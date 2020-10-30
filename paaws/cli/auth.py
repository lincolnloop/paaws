import json
import webbrowser
from functools import lru_cache
from pathlib import Path
from typing import Any
import logging

import click
from appdirs import user_cache_dir
import urllib3
import boto3
from paaws.utils import fail, success

log = logging.getLogger(__name__)

AUTH0_APP_URL = "https://dev-cehlend0.us.auth0.com"
DEVICE_CODE_URL = f"{AUTH0_APP_URL}/oauth/device/code"
OAUTH_TOKEN_URL = f"{AUTH0_APP_URL}/oauth/token"
USER_INFO_URL = f"{AUTH0_APP_URL}/userinfo"
CLIENT_ID = "x15zAd2hgdbugNWSZz2mP2k5jcZfNFk3"
SCOPE = "openid profile email offline_access"
AUDIENCE = "https://paaws.lloop.us"
GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"
CACHE_DIR = Path(user_cache_dir(appname="paaws", appauthor="LincolnLoop"))


def write_to_cache(key: str, value: Any) -> None:
    """Write a JSON serializable value to the user's filesystem cache"""
    CACHE_DIR.mkdir(0o700, exist_ok=True)
    (CACHE_DIR / key).write_text(json.dumps(value))
    (CACHE_DIR / key).chmod(0o600)


def read_from_cache(key: str) -> Any:
    """Retrieve a value from the user's filesystem cache"""
    return json.loads((CACHE_DIR / key).read_text())


def post_json(url: str, json_dict: dict) -> urllib3.response.HTTPResponse:
    """Post dict as JSON and decode JSON response"""
    http = urllib3.PoolManager()
    resp = http.request(
        "POST",
        url,
        body=json.dumps(json_dict).encode(),
        headers={"Content-Type": "application/json"},
    )
    if resp.status != 200:
        fail(f"Request to {url} failed. Status {resp.status}")
    return json.loads(resp.data.decode())


@click.command()
def login():
    """Authorize CLI"""
    device_code_resp = post_json(
        DEVICE_CODE_URL, {"client_id": CLIENT_ID, "scope": SCOPE, "audience": AUDIENCE}
    )
    print(f"Your verification code is {device_code_resp['user_code']}")
    webbrowser.open(device_code_resp["verification_uri_complete"])
    input("Finish verification in your web browser then press ENTER to continue.")
    oauth_token_resp = post_json(
        OAUTH_TOKEN_URL,
        {
            "grant_type": GRANT_TYPE,
            "device_code": device_code_resp["device_code"],
            "client_id": CLIENT_ID,
        },
    )
    write_to_cache("tokens", oauth_token_resp)
    user_info = get_user_info(oauth_token_resp["access_token"])
    success(f"Logged in as {user_info['email']}")


@click.command()
def whoami():
    print(get_email())


def get_email():
    tokens, user_info = verify_auth()
    return user_info["email"]


def get_user_info(access_token: str = None) -> dict:
    """Fetch user info from Auth0"""
    # we could decode this with `jwt.decode(oauth_token_resp["id_token"], verify=False)`, but that
    # takes requires installing cryptography which will be hard to distribute. We can just fetch the data decoded
    # from the API instead.
    if not access_token:
        access_token = read_from_cache("tokens")["access_token"]
    http = urllib3.PoolManager()
    log.debug("Fetching user info")
    user_info_resp = http.request(
        "GET", USER_INFO_URL, headers={"Authorization": f"Bearer {access_token}"}
    )
    if user_info_resp.status != 200:
        return fail(
            f"Request to {USER_INFO_URL} failed. Status {user_info_resp.status}"
        )
    userinfo = json.loads(user_info_resp.data.decode())
    write_to_cache("user", userinfo)
    return userinfo


def refresh_tokens():
    """Refresh Auth0 tokens"""
    tokens = read_from_cache("tokens")
    log.debug("Refreshing auth token")
    oauth_token_resp = post_json(
        OAUTH_TOKEN_URL,
        {
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
            "client_id": CLIENT_ID,
        },
    )
    write_to_cache("tokens", oauth_token_resp)
    return oauth_token_resp


def verify_auth() -> (dict, dict):
    try:
        tokens = read_from_cache("tokens")
    except FileNotFoundError:
        return fail("Not logged in. Run `paaws login`")
    try:
        user_info = read_from_cache("user")
    except FileNotFoundError:
        user_info = get_user_info(tokens["access_token"])
    return tokens, user_info


@lru_cache(maxsize=2)
def get_credentials(app_name) -> dict:
    """Trade Auth0 token for AWS credentials"""
    tokens, user_info = verify_auth()
    # if user doesn't have a role for the app, try refreshing the user_info
    try:
        role_arn = user_info["https://paaws.lloop.us/aws_roles"][app_name]
    except KeyError:
        log.debug(
            "No access to %s. Refreshing tokens to check for new access.", app_name
        )
        tokens = refresh_tokens()
        user_info = get_user_info(tokens["access_token"])
        try:
            role_arn = user_info["https://paaws.lloop.us/aws_roles"][app_name]
        except KeyError:
            return fail(f"You don't have access to {app_name}")
    sts = boto3.client("sts")
    kwargs = dict(
        RoleArn=role_arn,
        WebIdentityToken=tokens["id_token"],
        RoleSessionName=user_info["email"],
        DurationSeconds=900,
    )
    try:
        log.debug("Fetching AWS credentials for %s", role_arn)
        return sts.assume_role_with_web_identity(**kwargs)["Credentials"]
    except sts.exceptions.ExpiredTokenException:
        tokens = refresh_tokens()
        kwargs["WebIdentityToken"] = tokens["id_token"]
        log.debug("Fetching AWS credentials for %s", role_arn)
        return sts.assume_role_with_web_identity(**kwargs)["Credentials"]
