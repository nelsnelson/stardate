stardate
========

![favicon.ico][favicon]

Tiny API server for git project version information.

Easily check the version of your app.

To install, change directory into your git version-controlled project and run:
```{sh}
curl --silent https://raw.githubusercontent.com/nelsnelson/stardate/master/install.sh --output - | sh
```


Example:

```{sh}
$ curl --silent http://localhost:47988 | python3.7 -m json.tool
{
    "version": {
        "author": "Nels Nelson <nels@nelsnelson.org>",
        "commit": "0d96e6d37f19770022a0b5be3f7694a809ae5fb5",
        "date": "Sat Sep 5 09:26:44 2015 -0500",
        "message": "Initial commit"
    }
}

```


The program will also serve git version information for multiple projects.

Any directory in which the server is started will be scanned, and sub-directories which are version-controlled by git will be indexed.  Just navigate to http://0.0.0.0:47988/index.html in your browser to see a listing of all scanned projects.

[favicon]: https://raw.githubusercontent.com/nelsnelson/stardate/master/favicon.ico
