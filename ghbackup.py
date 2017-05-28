#! /usr/bin/env python3

import argparse
import concurrent.futures as cf
import itertools
import logging
import os
import sys
import urllib.parse as urlp

from typing import Any, Callable, List, Mapping, Optional, Tuple

from agithub.GitHub import GitHub
import git
import yaml


DEFAULT_CONF_PATH = "./ghbackup.yml"

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


def info(txt: str, *args, **kwargs) -> None:
    logging.info(txt.format(*args, **kwargs))


def error(txt: str, *args, **kwargs) -> None:
    logging.error("Error: " + txt.format(*args, **kwargs))


def sprint(txt: str, *args, **kwargs) -> None:
    print(txt.format(*args, **kwargs), flush=True)


def gen_default_conf(conf_path: str, token: str) -> None:
    repopath = os.path.join(os.getcwd(), 'repos')
    if token == "":
        body = DEFAULT_CONF_BODY.format(repopath=repopath,
                                        token='# token: "XXXXXXXX"')
    else:
        body = DEFAULT_CONF_BODY.format(repopath=repopath,
                                        token='  token: "{}"'.format(token))
    with open(conf_path, "w") as conf_file:
        conf_file.write(body)


def paginate(path: Callable, per_page: int = 30, **kwargs) -> Tuple[int, List[Mapping]]:
    output = []
    for page in itertools.count(1):
        status, rsp = path(page=page, per_page=per_page, **kwargs)

        if status != 200:
            return status, rsp

        rsps = len(rsp)
        if rsps == 0:
            break  # Empty page means we are done
        else:
            output += rsp
            if rsps < per_page:
                break  # Non-full page must be last
    return 200, output


def test_token(ghub: GitHub) -> Optional[Mapping]:
    ret, rsp = ghub.user.get()
    if ret == 401:
        error("Failed to authenticate to github. Please check the value of token.")
    elif ret == 403:
        error("You have tried to connect too many times with "
              "an invalid token. Please wait and try again later.")
    elif ret == 200:
        return rsp
    else:
        error("Access to github returned code {} and response:\n{}", ret, rsp)
    return None


def load_repos(ghub: GitHub, only_personal: bool) -> Optional[Mapping[str, Mapping]]:
    if only_personal:
        status, repos = paginate(ghub.user.repos.get, affiliation="owner")
    else:
        status, repos = paginate(ghub.user.repos.get)
    if status == 200:
        return {repo['name']: repo for repo in repos}
    else:
        return None


def conf_load(conf: Mapping[str, Any], *args, default: Any = None) -> Any:
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


def embed_auth_in_url(url: str, user: str, token: str) -> str:
    urlparts = urlp.urlsplit(url)
    url_netloc = "{}:{}@{}".format(user, token, urlparts.netloc)
    return urlp.urlunsplit((urlparts.scheme,
                            url_netloc,
                            urlparts.path,
                            urlparts.query,
                            urlparts.fragment))


def load_refs(repo) -> Mapping[str, str]:
    return {ref.name: ref.commit.hexsha for ref in repo.refs}


def update_repo(name: str, repo: Mapping, repopath: str, user: str, token: str) -> bool:
    repo_dir = os.path.join(repopath, name)
    url = embed_auth_in_url(repo['clone_url'], user, token)
    clone = not os.path.exists(repo_dir)
    try:
        if clone:
            git.Repo.clone_from(url,
                                os.path.join(repopath, name),
                                mirror=True)
            info("Cloned repo {} from {}", name, repo['clone_url'])
        else:
            g_repo = git.Repo(os.path.join(repopath, name, ''))
            if url != g_repo.remotes.origin.url:
                info("Repo url is incorrect, altering.")
                g_repo.remotes.origin.set_url(url,
                                              g_repo.remotes.origin.url)

            ref_snapshot = load_refs(g_repo)

            g_repo.remotes.origin.fetch()

            if ref_snapshot != load_refs(g_repo):
                info("Fetched repo {} - new changes", name)
            else:
                info("Fetched repo {}", name)
        return True
    except git.GitCommandNotFound:
        error("Failed to find git binary, please install git.")
    except git.NoSuchPathError:
        error("Cannot operate on repo path: {}", repo_dir)
    except git.InvalidGitRepositoryError:
        error("Problem with the repo contained in {}. "
              "If the repository still exists on GitHub, "
              "try deleting the local copy and retrieving a fresh clone.",
              repo_dir)
    except git.GitCommandError as exc:
        error("Git operation failed:\nArgs: {}\nOutput:\n{}",
              " ".join(exc.command),
              exc.stderr.strip()[9:-1])
    except (git.CommandError, git.CacheError):
        logging.exception("Exception encountered:")
    if clone:
        error("Failed to clone repo {} from {}", name, repo['clone_url'])
    else:
        error("Failed to fetch repo {}", name)
    return False


def check_unknown(unknown_repos: List[Mapping]) -> Tuple[Mapping[str, Mapping], List[str]]:
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
    parser.add_argument("--workers", "-j", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = gather_args()
    logging.basicConfig(format="{message}",
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
            error("Must either specify auth token on command line or in config.")
            return 1
    ghub = GitHub(token=auth)

    info("Testing auth token and loading user")
    user = test_token(ghub)

    if user is None:
        return 1
    else:
        user = user['login']

    repopath = conf_load(conf, 'general', 'repopath')
    if repopath is None:
        error("Config must specify a repopath in the general section.")
        return 1

    if not os.path.exists(repopath):
        info("Repo path does not exist, creating.")
        os.mkdir(repopath)

    only_personal = conf_load(conf,
                              'general', 'only_personal',
                              default=True)
    unknown_repo_warning = conf_load(conf,
                                     'general', 'unknown_repo_warning',
                                     default=5)

    info("Loading data from config")
    conf_repos = conf_load(conf, 'repos', default={})
    info("{} repos configured", len(conf_repos))
    exclude = conf_load(conf, 'exclude', default=[])
    info("{} repos excluded", len(exclude))

    info("Loading repo data from github")
    ghub_repos = load_repos(ghub, only_personal)

    if ghub_repos is None:
        error("Failed to retrieve repo data from GitHub")
        return 1

    unknown = [repo
               for name, repo in ghub_repos.items()
               if name not in conf_repos and name not in exclude]
    info("{} repos found on github of which {} are unknown", len(ghub_repos), len(unknown))

    if args.interactive and len(unknown) > 0:
        new_repos, new_exclude = check_unknown(unknown)
        conf_repos.update(new_repos)
        conf['repos'] = conf_repos
        conf['exclude'] = list(set(exclude) | set(new_exclude))
        with open(args.conf, "w") as conf_file:
            yaml.safe_dump(conf, conf_file, default_flow_style=False)

    info("Updating repositories")

    exit_code = 0

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(update_repo, name, repo, repopath, user, auth) for name, repo in conf_repos.items()]
        all_success = all([ftr.result() for ftr in cf.as_completed(futures)])
        if not all_success:
            error("Some repos failed to fetch or clone.")
            exit_code |= 4

    if not args.interactive:
        if 0 < unknown_repo_warning <= len(unknown):
            error("There are {} unknown repos on github. "
                  "This is more than your limit of {}.",
                  len(unknown),
                  unknown_repo_warning)
            exit_code |= 2
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
