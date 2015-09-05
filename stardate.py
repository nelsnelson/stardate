#! /usr/bin/env python

import argparse
import collections
import errno
import json
import logging
import os
import re
import socket
import subprocess
import sys
import BaseHTTPServer
import SimpleHTTPServer


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p", "--project-path",
        help="Path to project for which to serve version info",
        type=str, required=False, default=os.getcwd(),
    )
    parser.add_argument(
        "-m", "--message",
        help="Default commit message when revision is missing",
        type=str, required=False, default='Initial commit',
    )

    return parser.parse_args()


def execute(cmd, cwd=None, env=None):
    lines = []
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        close_fds=True)

    while proc.poll() is None:
        line = proc.stdout.readline()
        if line is None:
            break
        line = line.strip()
        if line == '':
            continue
        lines.append(line)

    returncode = proc.wait()

    return lines, proc.returncode


class App(object):
    log_format = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

    def __init__(self):
        global log
        log = logging.getLogger(self.__class__.__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(App.log_format)
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        self.handler = App.Handler
        self.handler.app = self

    def run(self, host='0.0.0.0', port=6000):
        server_address = (host, port)
        self.name = self.__class__.__name__
        self.protocol_version = 'HTTP/1.0'
        try:
            self.httpd = BaseHTTPServer.HTTPServer(
                server_address, self.handler)
            self.socket_address, self.socket_port = \
                self.httpd.socket.getsockname()
            log.info('Listening on {0}:{1}'.format(
                self.socket_address, self.socket_port))
            self.httpd.serve_forever()
        except socket.error:
            sys.stdout.write("\r")
            sys.stdout.flush()
            log.error('Already running on port {0}'.format(port))
            log.info('Terminating')
            sys.exit(0)
        except KeyboardInterrupt:
            sys.stdout.write("\r")
            sys.stdout.flush()
            log.info('Shutting down')
            self.stop()

    def stop(self):
        self.httpd.shutdown()
        sys.exit(0)

    class Handler(SimpleHTTPServer.SimpleHTTPRequestHandler):
        favicon_path = re.compile('\/favicon\.ico(\?.*)?')

        def __init__(self, *args):
            errors = []
            try:
                SimpleHTTPServer.SimpleHTTPRequestHandler.__init__(
                    self, *args)
            except IOError as e:
                errors.append(e)
                if e.errno == errno.EPIPE:
                    log.debug("Ignoring broken pipe error")
                else:
                    log.warning("Unhandled IOError: {}".format(e.message))
            if not errors:
                self.app = self.__class__.app

        def _send(self, data):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-length', len(data))
            self.end_headers()
            self.wfile.write(data)

        def log_request(self, code='-', size='-'):
            if self.favicon_path.match(self.path):
                return
            method = self.requestline
            host = self.address_string()
            log.info("%s from %s: %s" % (method, host, code))

        def do_GET(self):
            response = ''
            content_type = 'text/plain'
            if self.favicon_path.match(self.path):
                content_type = 'image/x-icon'
                try:
                    f = open('./favicon.ico', 'rb')
                    response = f.read()
                except:
                    log.error("Failed to serve %s resource" % (self.path))
                    pass
            else:
                try:
                    response, content_type = self.app.get(self.path)
                except NameError as e:
                    if re.compile("'app' is not defined").match(e.message):
                        log.error("Handler subclass must define app")
                        self.send_response(500)
                        self.wfile.write("Web application is misconfigured")
                        return
                    else:
                        raise e
            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Content-length', len(response))
            self.end_headers()
            self.wfile.write(response)
            # self._send(response)


class stardate(App):
    information = {
        'commit': re.compile('commit ([0-9a-z]+)'),
        'author': re.compile('Author:\s+([\w\s\<\>\@\.]+)'),
        'date': re.compile('Date:\s+(.+)'),
        'message': re.compile('(?!^(commit|Author:|Date:))([\w\s]+)'),
    }
    errors = {
        'not a git repository': re.compile('fatal: Not a git repository'),
        'bad default revision': re.compile('fatal: bad default revision'),
    }
    projects = []
    index = (
        '<html>\n'
        '<head>\n'
        '<title>Index</title></head>\n'
        '<body>\n'
        '<h1>Index</h1>\n'
        '<div>{}</div>\n'
        '</body>\n')
    anchor = '<a href="{}">{}</a><br />'

    def __init__(self, args):
        super(stardate, self).__init__()
        self.target = os.path.abspath(os.path.expanduser(args.project_path))
        self.message = args.message
        self.check_for_git()
        self.setup()

    def check_for_git(self):
        if not self.git_is_installed():
            log.error('Git is not installed')
            sys.exit(0)

    def setup(self):
        lines = self.git_log()
        if self.has_error(lines, 'not a git repository'):
            self.scan_for_git_projects()
        elif self.has_error(lines, 'bad default revision'):
            log.error(
                'Manual initialization of the git repository is required')
            sys.exit(0)

            log.info('Hosting version information for {0}'.format(
                self.target))

    def scan_for_git_projects(self):
        log.info('Scanning version information for {0}'.format(self.target))
        for directory, sub_directories, files in os.walk(self.target):
            if '.git' in sub_directories:
                log.info('Found a git project: {}'.format(directory))
                self.projects.append(directory[len(self.target):])

    def parse_info(self, lines):
        result = {}
        for info in self.information:
            for s in lines:
                match = self.information[info].match(s)
                if match:
                    i = len(match.groups())
                    result[info] = match.group(i)
                    break
        return result

    def has_error(self, lines, error):
        return (
            error in self.errors and
            any([self.errors[error].match(s) for s in lines])
        )

    def do(self, command):
        lines, _ = execute(command, cwd=self.target)
        return lines

    def git_is_installed(self):
        lines, code = execute('which git')
        return code == 0

    def git_log(self, project='./'):
        command = 'git log -n1'
        if project:
            command = 'pushd {}; {}'.format(project, command)
        return self.do(command)

    def git_version_for_current_directory(self):
        lines = self.git_log()
        version_info = self.parse_info(lines)
        content_type = 'application/json'
        return (json.dumps({'version': version_info}), content_type)

    def git_version_for_given_directory(self, path):
        lines = self.git_log(path[1:])
        version_info = self.parse_info(lines)
        content_type = 'application/json'
        return (json.dumps({'version': version_info}), content_type)

    def git_projects_index(self, path):
        anchors = [
            self.anchor.format(path, path[1:])
            for path in list(self.projects)]
        content_type = 'text/html'
        return (self.index.format('\n'.join(anchors)), content_type)

    def git_versions_for_all_projects(self):
        project_versions = {}
        for project in self.projects:
            lines = self.git_log(project[1:])
            version_info = self.parse_info(lines)
            project_versions[project[1:]] = version_info
        content_type = 'application/json'
        return (json.dumps({'projects': project_versions}), content_type)

    def get(self, path):
        try:
            if not self.projects:
                response, content_type = \
                    self.git_version_for_current_directory()
            elif path in self.projects:
                response, content_type = \
                    self.git_version_for_given_directory(path)
            elif re.compile('^/index(\.htm|\.html)?$').match(path):
                response, content_type = self.git_projects_index(path)
            else:
                response, content_type = self.git_versions_for_all_projects()
        except Exception as ex:
            log.error(ex.message)
            content_type = 'application/json'
            response = {'error': ex.message}

        return (response, content_type)


def main():
    args = parse_arguments()
    app = stardate(args)
    app.run(host='0.0.0.0', port=47988)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
