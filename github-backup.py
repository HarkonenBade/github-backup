#! /usr/bin/env python3

import argparse
import itertools
import os
import sys

from agithub.GitHub import GitHub
import yaml


DEFAULT_CONF_PATH = "./github-backup.yml"

DEFAULT_CONF_BODY = """
general:
{token}
  repopath: "{repopath}"
# Number of unknown repos required to prompt a warning in cron mode. (Default: 5, set to 0 to disable)
# unknown_repo_warning: 5
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
    if only_personal:
        repos = paginate(ghub.user.repos.get, affiliation="owner")
    else:
        repos = paginate(ghub.user.repos.get)
    return {repo['name']: repo for repo in repos if repo['name'] not in exclude}


def conf_load(conf, *args, default=None):
    cur = conf
    for step in args:
        if step in cur:
            cur = cur[step]
        else:
            return default
    return cur


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
        else:
            auth = conf_load(conf, 'general', 'token')
            if auth is None:
                print("Error: Must either specify auth token on command line or in config.")
                sys.exit(1)
        ghub = GitHub(token=auth)

        only_personal = conf_load(conf, 'general', 'only_personal', default=True)
        unknown_repo_warning = conf_load(conf, 'general', 'unknown_repo_warning', default=5)
        exclude = conf_load(conf, 'exclude', default=[])
        conf_repos = conf_load(conf, 'repos', default=[])
        ghub_repos = load_repos(ghub, only_personal, exclude)

        unknown = [repo for name, repo in ghub_repos.items() if name not in conf_repos]

        if args.cron:
            if 0 < unknown_repo_warning <= len(unknown):
                print("Error: There are {} unknown repos on github. "
                      "This is more than your limit of {}.".format(unknown, unknown_repo_warning))
                sys.exit(2)


if __name__ == "__main__":
    main()
