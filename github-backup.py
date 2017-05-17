#! /usr/bin/env python3

import argparse
import itertools
import logging
import os
import sys
import urllib.parse as urlp

from agithub.GitHub import GitHub
import git
import yaml


DEFAULT_CONF_PATH = "./github-backup.yml"

DEFAULT_CONF_BODY = """
general:
  repopath: "{repopath}"
  # Github Personal Access Token
  # Created at: https://github.com/settings/tokens
  # Must have the 'repo' scope to access private as well as public repos
{token}
  # Number of unknown repos required to prompt a warning in
  # non-interactive mode. (Default: 5, set to 0 to disable)
  unknown_repo_warning: 5
  # Only look for repos owned by the authed user (Default: true)
  only_personal: true
repos: {{}}
exclude: []"""


def info(txt, *args, **kwargs):
    logging.info(txt.format(*args, **kwargs))


def error(txt, *args, **kwargs):
    logging.error(txt.format(*args, **kwargs))


def sprint(txt, *args, **kwargs):
    print(txt.format(*args, **kwargs), flush=True)


def gen_default_conf(conf_path, token):
    repopath = os.path.join(os.getcwd(), 'repos')
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


def test_token(ghub):
    ret, _ = ghub.user.get()
    if ret != 200:
        error("Auth token does not seem to be valid. "
              "Please check the value of token.")
        sys.exit(1)


def load_repos(ghub, only_personal, exclude):
    if only_personal:
        repos = paginate(ghub.user.repos.get, affiliation="owner")
    else:
        repos = paginate(ghub.user.repos.get)
    return {repo['name']: repo
            for repo in repos
            if repo['name'] not in exclude}


def conf_load(conf, *args, default=None):
    cur = conf
    for step in args:
        if step in cur:
            cur = cur[step]
        else:
            return default
    if cur is None:
        return default
    else:
        return cur


def embed_auth_in_url(url, user, token):
    urlparts = urlp.urlsplit(url)
    url_netloc = "{}:{}@{}".format(user, token, urlparts.netloc)
    return urlp.urlunsplit(urlparts._replace(netloc=url_netloc))


def update_repos(repos, repopath, user, token):
    for name, repo in repos.items():
        repo_dir = os.path.join(repopath, name)
        url = embed_auth_in_url(repo['clone_url'], user, token)
        if os.path.exists(repo_dir):
            info("Updating repo {}", name)
            g_repo = git.Repo(os.path.join(repopath, name, ''))
            if url != g_repo.remotes.origin.url:
                info("Repo url is incorrect, altering.")
                g_repo.remotes.origin.set_url(url,
                                              g_repo.remotes.origin.url)
            g_repo.remotes.origin.fetch()
        else:
            info("Cloning repo {} from {}", name, repo['clone_url'])
            git.Repo.clone_from(url,
                                os.path.join(repopath, name),
                                mirror=True)


def check_unknown(unknown_repos):
    sprint("{} unknown repos found while checking github, "
           "please classify them:",
           len(unknown_repos))
    new_repos = {}
    new_exclude = []
    for repo in unknown_repos:
        sprint("Name: {}\n"
               "Fork: {}\n"
               "URL: {}\n"
               "Description: {}",
               repo['name'],
               "Yes" if repo['fork'] else "No",
               repo['url'],
               repo['description'])
        while True:
            choice = input("(Y)es/(N)o/(S)kip? ").upper()
            if choice in ["Y", "N", "S"]:
                break
        sprint("")
        if choice == "Y":
            sprint("Adding {} to the list of repos.\n", repo['name'])
            new_repos[repo['name']] = {'clone_url': repo['clone_url']}
        elif choice == "N":
            sprint("Adding {} to the exclusion list.\n", repo['name'])
            new_exclude.append(repo['name'])
        else:
            sprint("Skipping {} for this run.\n", repo['name'])
    return new_repos, new_exclude


def gather_args():
    parser = argparse.ArgumentParser(description="A github mirroring tool.")
    parser.add_argument("--conf", default=DEFAULT_CONF_PATH)
    parser.add_argument("--token", default="")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main():
    args = gather_args()
    logging.basicConfig(format="{levelname} {message}",
                        style="{",
                        level=logging.ERROR if args.quiet else logging.INFO)
    if not os.path.exists(args.conf):
        info("No config file found, generating a bare-bones one.")
        gen_default_conf(args.conf, args.token)

    with open(args.conf, "r") as conf_file:
        conf = yaml.safe_load(conf_file)

    if args.token != "":
        auth = args.token
    else:
        auth = conf_load(conf, 'general', 'token')
        if auth is None:
            error("Must either specify auth token "
                  "on command line or in config.")
            sys.exit(1)
    ghub = GitHub(token=auth)

    test_token(ghub)

    ghub_user = ghub.user.get()[1]['login']

    repopath = conf_load(conf, 'general', 'repopath')
    if repopath is None:
        error("Config must specify a repopath in the general section.")
        sys.exit(1)

    if not os.path.exists(repopath):
        info("Repo path does not exist, creating.")
        os.mkdir(repopath)

    only_personal = conf_load(conf,
                              'general', 'only_personal',
                              default=True)
    unknown_repo_warning = conf_load(conf,
                                     'general', 'unknown_repo_warning',
                                     default=5)
    exclude = conf_load(conf, 'exclude', default=[])
    conf_repos = conf_load(conf, 'repos', default={})
    ghub_repos = load_repos(ghub, only_personal, exclude)

    unknown = [repo
               for name, repo in ghub_repos.items()
               if name not in conf_repos]

    if args.interactive and len(unknown) > 0:
        new_repos, new_exclude = check_unknown(unknown)
        conf_repos.update(new_repos)
        conf['repos'] = conf_repos
        conf['exclude'] = list(set(exclude) | set(new_exclude))
        with open(args.conf, "w") as conf_file:
            yaml.safe_dump(conf, conf_file, default_flow_style=False)

    update_repos(conf_repos, repopath, ghub_user, auth)

    if not args.interactive:
        if 0 < unknown_repo_warning <= len(unknown):
            error("There are {} unknown repos on github. "
                  "This is more than your limit of {}.",
                  len(unknown),
                  unknown_repo_warning)
            sys.exit(2)


if __name__ == "__main__":
    main()
