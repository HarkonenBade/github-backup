#! /usr/bin/env python3

import argparse
import itertools
from pprint import pprint
import os
import sys

from agithub.GitHub import GitHub
import yaml


DEFAULT_CONF_PATH = "./github-backup.yml"

DEFAULT_CONF_BODY = """
general:
{token}
  repopath: "{repopath}"
  unknown_repo_warning: 5
# Only look for repos owned by the authed user (Default: true)
# only_personal: false
repos: {{}}
exclude: []"""


def gen_default_conf(conf_path, token):
    repopath = os.getcwd()
    if token == "":
        body = DEFAULT_CONF_BODY.format(repopath=repopath,
                                        token='# token: "XXXXXXXX"')
    else:
        body = DEFAULT_CONF_BODY.format(repopath=repopath,
                                        token='  token: "{}"'.format(token))
    with open(conf_path, "w") as conf_file:
        conf_file.write(body)


def paginate(path, per_page=30, **kwargs):
    for page in itertools.count(1):
        status, rsp = path(page=page, per_page=per_page, **kwargs)
        rsps = len(rsp)
        if rsps == 0:
            break  # Empty page means we are done
        else:
            for elm in rsp:
                yield elm
            if rsps < per_page:
                break  # Non-full page must be last


def load_repos(ghub, only_personal, exclude):
    repos = paginate(ghub.user.repos.get)
    _, me = ghub.user.get()
    pprint([repo['name'] for repo in repos if repo['owner']['id'] == me['id'] and not repo['fork']])


def gather_args():
    parser = argparse.ArgumentParser(description="A github mirroring tool.")
    parser.add_argument("--conf", default=DEFAULT_CONF_PATH)
    parser.add_argument("--token", default="")
    parser.add_argument("--cron", action="store_true")
    parser.add_argument("--gen-conf", action="store_true")
    return parser.parse_args()


def main():
    args = gather_args()

    if args.gen_conf:
        gen_default_conf(args.conf, args.token)
    else:
        with open(args.conf, "r") as conf_file:
            conf = yaml.safe_load(conf_file)

        if args.token != "":
            auth = args.token
        elif 'general' in conf and 'token' in conf['general']:
            auth = conf['general']['token']
        else:
            print("Error: Must either specify auth token on command line or in config.")
            sys.exit(1)
        ghub = GitHub(token=auth)

        if 'general' in conf and 'only_personal' in conf['general']:
            only_personal = conf['general']['only_personal']
        else:
            only_personal = True

        if 'exclude' in conf:
            exclude = conf['exclude']
        else:
            exclude = []

        if 'repos' in conf:
            conf_repos = conf['repos']
        else:
            conf_repos = []

        ghub_repos = load_repos(ghub, only_personal, exclude)


if __name__ == "__main__":
    main()
