#! /usr/bin/env sh

stardate_repository='git@github.com:nelsnelson/stardate.git';
target_directory="${HOME}/.stardate";
server='stardate.py';
wd=`pwd`;
python=`which python`;
git=`which git`;

if [ ! -f ${python} ]; then
    echo 'fatal: python is not installed';
    exit 1;
fi

if [ ! -f ${git} ]; then
    echo 'fatal: git is not installed';
    exit 1;
fi

if [ -d ${target_directory} ]; then
    pushd ${target_directory} &>/dev/null;
    ${git} fetch origin
    ${git} reset --hard origin/master;
    popd &>/dev/null;
else
    ${git} clone ${stardate_repository} ${target_directory};
fi

# TODO Install stardate.sh as a systemd service
`${python} ${target_directory}/${server} --project-path ${wd}`;
