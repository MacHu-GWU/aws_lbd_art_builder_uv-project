---
name: pypi-boto_session_manager
description: "boto_session_manager (v2.1.0): a high-level boto3 wrapper that creates and caches AWS sessions, clients, and resources, with typed lazy client properties for 430+ services, assume role (optionally auto-refreshing), AWS CLI env-var injection, and credential snapshots. Public API: BotoSesManager, AwsServiceEnum, PATH_DEFAULT_SNAPSHOT, NoBotocoreCredentialError. Use when code imports boto_session_manager, mentions BotoSesManager or bsm, or needs boto3 sessions, assumed IAM roles, or typed AWS clients."
---

# boto_session_manager 2.1.0

`BotoSesManager` wraps a `boto3.Session` and is the single entry point: it lazily creates and caches the session, every client and resource, and the caller identity. Each AWS service has a typed property such as `bsm.s3_client`, typed via `mypy-boto3-*` stubs (`pip install "boto3-stubs[all]"` for full IDE autocomplete). `assume_role` returns a new, independent `BotoSesManager`. Requires Python 3.11+ and a user-installed `boto3` (a peer dependency).

## Import

```python
from boto_session_manager.api import BotoSesManager
import boto_session_manager.api as boto_session_manager     # then boto_session_manager.BotoSesManager
```

## Public API

- `BotoSesManager(aws_access_key_id=..., aws_secret_access_key=..., aws_session_token=..., region_name=..., botocore_session=..., profile_name=..., default_client_kwargs=..., expiration_time=...)`: every argument optional; omitted ones fall back to the boto3 credential chain. `default_client_kwargs` is merged into every `get_client`/`get_resource` call (e.g. `{"endpoint_url": "http://localhost:4566"}`).
  - `.boto_ses -> boto3.session.Session`: cached session. `.create_boto_ses()` builds a fresh, uncached one.
  - `.<service>_client`: typed cached client for each service, e.g. `s3_client`, `ec2_client`, `lambda_client`, `dynamodb_client`, `sts_client`, `iam_client`.
  - `.get_client(service_name: str, region_name=..., endpoint_url=..., config=..., ...) -> BaseClient`: cached by `service_name` only.
  - `.get_resource(service_name: str, ...) -> ServiceResource`: same, for the boto3 resource interface.
  - `.aws_account_id -> str`, `.aws_account_user_id -> str`, `.principal_arn -> str`: cached, one STS `get_caller_identity` call.
  - `.masked_aws_account_id`, `.masked_aws_account_user_id`, `.masked_principal_arn -> str`: masked for logs.
  - `.aws_region -> str`, `.aws_account_alias -> str | None` (one IAM call): cached.
  - `.print_who_am_i(masked: bool = True)`: prints user id, account, ARN, alias, region.
  - `.assume_role(role_arn: str, role_session_name=..., duration_seconds: int = 3600, tags=..., transitive_tag_keys=..., external_id=..., mfa_serial_number=..., mfa_token=..., source_identity=..., region_name=..., auto_refresh: bool = False) -> BotoSesManager`: new manager under the role; region defaults to the current one.
  - `.is_expired(delta: int = 0) -> bool`: True if credentials expire within `delta` seconds.
  - `.awscli()`: context manager; sets `AWS_*` env vars for subprocesses, restores them on exit.
  - `.to_snapshot() -> dict`: credentials and region as a dict.
  - `BotoSesManager.from_snapshot(snapshot: dict) -> BotoSesManager` (classmethod).
  - `BotoSesManager.from_snapshot_file(path=PATH_DEFAULT_SNAPSHOT) -> BotoSesManager` (classmethod).
  - `.temp_snapshot(path=PATH_DEFAULT_SNAPSHOT)`: context manager; writes a snapshot JSON file, deletes it on exit.
  - `.clear_cache()`: drops the cached session, clients, resources, and identity.
- `AwsServiceEnum`: string constants of boto3 service ids, named after boto3 client classes, e.g. `AwsServiceEnum.S3 == "s3"`, `AwsServiceEnum.DynamoDB == "dynamodb"`, `AwsServiceEnum.ACMPCA == "acm-pca"`. The typed property is the lower-cased attribute + `_client` (`acmpca_client`).
- `PATH_DEFAULT_SNAPSHOT: Path`: `~/.bsm-snapshot.json`.
- `NoBotocoreCredentialError(Exception)`: raised by `assume_role(auto_refresh=True)` when the source session has no credentials.

## Common usage

```python
from boto_session_manager.api import BotoSesManager, AwsServiceEnum

bsm = BotoSesManager(profile_name="my_profile", region_name="us-east-1")
bsm.s3_client.list_buckets()
assert bsm.get_client(AwsServiceEnum.S3) is bsm.s3_client
print(bsm.aws_account_id, bsm.aws_region)

# assumed role; auto_refresh=True keeps long-running processes alive
bsm_role = bsm.assume_role(
    role_arn="arn:aws:iam::111122223333:role/my-role",
    duration_seconds=900,
    auto_refresh=True,
)

# hand credentials to the AWS CLI
import subprocess
with bsm_role.awscli():
    subprocess.run(["aws", "sts", "get-caller-identity"])

# hand credentials to another process
with bsm.temp_snapshot():
    subprocess.run(["python", "child.py"])  # child: BotoSesManager.from_snapshot_file()
```

## Gotchas

- Clients and resources are cached by service name: extra `get_client` kwargs are ignored once that service is cached. Use `default_client_kwargs`, a separate manager, or `clear_cache()`.
- Identity properties are cached; call `clear_cache()` after credentials change.
- `auto_refresh=True` relies on botocore internals (`DeferredRefreshableCredentials`), not public botocore API.
- `assume_role(external_id=...)` without `auto_refresh=True` fails with a parameter validation error before 2.1.0; require `boto_session_manager>=2.1.0` when passing an external id.
- A property for a service newer than the installed boto3 exists but fails when accessed; upgrade boto3. Services AWS retired are not properties any more (2.1.0 removed `iotevents`, `iotevents-data`, `panorama`, `simspaceweaver`); use `bsm.get_client("<service id>")`.

## More detail

For full API docs see `ref/public-api.md`.
