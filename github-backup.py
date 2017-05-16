#! /usr/bin/env python3

import argparse
import itertools
import os
import sys

from agithub.GitHub import GitHub
import git
import yaml


DEFAULT_CONF_PATH = "./github-backup.yml"

DEFAULT_CONF_BODY = """
general:
  repopath: "{repopath}"
{token}
# Number of unknown repos required to prompt a warning in non-interactive mode. (Default: 5, set to 0 to disable)
# unknown_repo_warning: 5
# Only look for repos owned by the authed user (Default: true)
# only_personal: false
repos: {{}}
exclude: []"""


def sprint(txt, *args, **kwargs):
    print(txt.format(*args, **kwargs), flush=True)


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


def update_repos(repos, repopath):
    for name, repo in repos.items():
        sprint("Updating {}...", name)
        g_repo = git.Repo(os.path.join(repopath, name, ''))
        if repo['clone_url'] != g_repo.remotes.origin.url:
            sprint("Repo url is incorrect, altering.")
            g_repo.remotes.origin.set_url(repo['clone_url'], g_repo.remotes.origin.url)
        g_repo.remotes.origin.fetch()


def clone_repo(repo, repopath):
    sprint("Cloning repo {} from {}", repo['name'], repo['clone_url'])
    git.Repo.clone_from(repo['clone_url'], os.path.join(repopath, repo['name']), mirror=True)


def check_unknown(unknown_repos, repopath):
    sprint("{} unknown repos found while checking github, please classify them:", len(unknown_repos))
    new_repos = {}
    new_exclude = []
    for repo in unknown_repos:
        sprint("Name: {} Fork?: {}",
               repo['name'],
               "Yes" if repo['fork'] else "No")
        while True:
            choice = input("(A)dd/(S)kip/(E)xclude? ").upper()
            if choice in ["A", "S", "E"]:
                break
        if choice == "A":
            sprint("Adding {} to the list of repos.", repo['name'])
            new_repos[repo['name']] = {'clone_url': repo['clone_url']}
            clone_repo(repo, repopath)
        elif choice == "E":
            sprint("Adding {} to the exclusion list.", repo['name'])
            new_exclude.append(repo['name'])
        else:
            sprint("Skipping {} for this run.", repo['name'])
    return new_repos, new_exclude


def gather_args():
    parser = argparse.ArgumentParser(description="A github mirroring tool.")
    parser.add_argument("--conf", default=DEFAULT_CONF_PATH)
    parser.add_argument("--token", default="")
    parser.add_argument("--interactive", action="store_true")
    return parser.parse_args()


def main():
    args = gather_args()

    if not os.path.exists(args.conf):
        sprint("No config file found, generating a bare-bones one.")
        gen_default_conf(args.conf, args.token)

    with open(args.conf, "r") as conf_file:
        conf = yaml.safe_load(conf_file)

    if args.token != "":
        auth = args.token
    else:
        auth = conf_load(conf, 'general', 'token')
        if auth is None:
            sprint("Error: Must either specify auth token on command line or in config.")
            sys.exit(1)
    ghub = GitHub(token=auth)

    repopath = conf_load(conf, 'general', 'repopath')
    if repopath is None:
        sprint("Error: Config must specify a repopath in the general section.")
        sys.exit(1)

    if not os.path.exists(repopath):
        os.mkdir(repopath)

    only_personal = conf_load(conf, 'general', 'only_personal', default=True)
    unknown_repo_warning = conf_load(conf, 'general', 'unknown_repo_warning', default=5)
    exclude = conf_load(conf, 'exclude', default=[])
    conf_repos = conf_load(conf, 'repos', default={})
    ghub_repos = load_repos(ghub, only_personal, exclude)

    unknown = [repo for name, repo in ghub_repos.items() if name not in conf_repos]

    if args.interactive:
        new_repos, new_exclude = check_unknown(unknown, repopath)
        conf['repos'].update(new_repos)
        conf['exclude'].update(exclude)
        with open(args.conf, "w") as conf_file:
            yaml.safe_dump(conf, conf_file)

    update_repos(conf_repos, repopath)

    if not args.interactive:
        if 0 < unknown_repo_warning <= len(unknown):
            sprint("Error: There are {} unknown repos on github. "
                   "This is more than your limit of {}.",
                   unknown,
                   unknown_repo_warning)
            sys.exit(2)


if __name__ == "__main__":
    main()
