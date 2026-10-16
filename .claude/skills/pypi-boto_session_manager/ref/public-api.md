# boto_session_manager 2.1.0: Public API Reference

```python
from boto_session_manager.api import BotoSesManager
from boto_session_manager.api import AwsServiceEnum
from boto_session_manager.api import PATH_DEFAULT_SNAPSHOT
from boto_session_manager.api import NoBotocoreCredentialError
```

"Omitted" below means the argument was not passed: the library uses an internal sentinel, so an omitted argument is never forwarded to boto3, and boto3's own default or credential chain applies.

## BotoSesManager

```python
BotoSesManager(
    aws_access_key_id: str | None = ...,
    aws_secret_access_key: str | None = ...,
    aws_session_token: str | None = ...,
    region_name: str | None = ...,
    botocore_session: botocore.session.Session | None = ...,
    profile_name: str = ...,
    default_client_kwargs: dict = ...,
    expiration_time: datetime = ...,
)
```

| Argument | Meaning |
| :--- | :--- |
| `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`, `region_name`, `botocore_session`, `profile_name` | Passed to `boto3.session.Session` when given. |
| `default_client_kwargs` | Merged into the kwargs of every `get_client` / `get_resource` call (explicit kwargs win). Inherited by `assume_role`. Default `{}`. |
| `expiration_time` | Timezone-aware `datetime` used by `is_expired`. Default: now + 365 days. `assume_role` sets it from the STS response. |

Construction is free: no AWS call happens until a client makes a request or an identity property is read.

```python
bsm = BotoSesManager()                                   # default credential chain
bsm = BotoSesManager(profile_name="my_profile")          # named profile
bsm = BotoSesManager(
    aws_access_key_id="AKIA...",
    aws_secret_access_key="...",
    region_name="us-east-1",
)
bsm = BotoSesManager(default_client_kwargs={"endpoint_url": "http://localhost:4566"})  # LocalStack
```

### Session

- `boto_ses -> boto3.session.Session` (property): created on first access, then cached.
- `create_boto_ses() -> boto3.session.Session`: a new, uncached session from the same arguments.

### Clients and resources

```python
get_client(
    service_name: str,
    region_name: str = ...,
    api_version: str = ...,
    use_ssl: bool = True,
    verify: bool | str = ...,
    endpoint_url: str = ...,
    aws_access_key_id: str = ...,
    aws_secret_access_key: str = ...,
    aws_session_token: str = ...,
    config: botocore.config.Config = ...,
) -> botocore.client.BaseClient

get_resource(...same arguments...) -> boto3.resources.base.ServiceResource
```

- The cache key is `service_name` only. The kwargs apply on the first call for that service; later calls return the cached object and ignore them. For a client with different settings, use another `BotoSesManager`, or `clear_cache()` first.
- `service_name` is any boto3 service id; `AwsServiceEnum` holds them as constants.

Typed properties, one per service, generated in `ClientMixin`: `bsm.<name>_client`, where `<name>` is the lower-cased `AwsServiceEnum` attribute (`s3_client`, `ec2_client`, `lambda_client`, `dynamodb_client`, `sqs_client`, `sns_client`, `iam_client`, `sts_client`, `secretsmanager_client`, `ssm_client`, `cloudformation_client`, `acmpca_client` for `acm-pca`, ...). Each returns `self.get_client(AwsServiceEnum.<X>)`, typed as `mypy_boto3_<service>.Client`, so the property and `get_client` share one cache. Types appear only when the matching stubs are installed (`boto3-stubs[s3]` or `boto3-stubs[all]`); there is no runtime cost.

```python
bsm.s3_client.put_object(Bucket="my-bucket", Key="key", Body=b"data")
s3 = bsm.get_client(AwsServiceEnum.S3)
assert s3 is bsm.s3_client
s3_resource = bsm.get_resource(AwsServiceEnum.S3)
```

### Identity (all cached until `clear_cache()`)

| Property | Type | Source | Example |
| :--- | :--- | :--- | :--- |
| `aws_account_id` | `str` | STS `get_caller_identity` | `"123456789012"` |
| `aws_account_user_id` | `str` | same call | `"AIDA..."` |
| `principal_arn` | `str` | same call | `"arn:aws:iam::123456789012:user/me"` |
| `masked_aws_account_id` | `str` | derived | `"12********12"` |
| `masked_aws_account_user_id` | `str` | derived (first 4 + `***` + last 4) | `"A1B2***IJKL"` |
| `masked_principal_arn` | `str` | derived (account part masked) | `"arn:aws:iam::12********12:user/me"` |
| `aws_region` | `str` | `boto_ses.region_name`, no AWS call | `"us-east-1"` |
| `aws_account_alias` | `str \| None` | IAM `list_account_aliases`, first alias | `"my-alias"` |

The three STS-backed properties share one call. `aws_account_alias` needs the `iam:ListAccountAliases` permission.

`print_who_am_i(masked: bool = True) -> None` prints user id, account id, principal ARN (masked unless `masked=False`), alias, and region.

### assume_role

```python
assume_role(
    role_arn: str,
    role_session_name: str = ...,             # default: a random uuid4 hex
    duration_seconds: int = 3600,
    tags: list[dict[str, str]] | None = ...,  # [{"Key": "...", "Value": "..."}]
    transitive_tag_keys: list[str] | None = ...,
    external_id: str = ...,
    mfa_serial_number: str = ...,
    mfa_token: str = ...,
    source_identity: str = ...,
    region_name: str = ...,                   # default: self.aws_region
    auto_refresh: bool = False,
) -> BotoSesManager
```

Returns a new, independent `BotoSesManager` with its own caches; `default_client_kwargs` carries over.

- `auto_refresh=False`: one STS `AssumeRole` call; the new manager holds static temporary credentials and `expiration_time` from the response. Check `is_expired()` in long jobs.
- `auto_refresh=True`: no immediate STS call. The new manager uses botocore's `AssumeRoleCredentialFetcher` + `DeferredRefreshableCredentials`, which assume the role lazily and refresh before expiry, as long as the source credentials stay valid. `expiration_time` is set to 2099-12-31, so `is_expired()` stays False. These are botocore internals, not public API. Raises `NoBotocoreCredentialError` if the source session has no credentials.

```python
bsm_role = bsm.assume_role(
    role_arn="arn:aws:iam::111122223333:role/my-role",
    duration_seconds=900,
    tags=[{"Key": "Project", "Value": "demo"}],
    region_name="eu-west-1",
)
bsm_role.sts_client.get_caller_identity()

# a role whose trust policy requires an external id (fixed in 2.1.0; broken
# before without auto_refresh=True)
bsm_partner = bsm.assume_role(
    role_arn="arn:aws:iam::111122223333:role/partner-role",
    external_id="my-external-id",
)
```

### is_expired

`is_expired(delta: int = 0) -> bool`: `now(UTC) + delta seconds >= expiration_time`. Use `delta` as a safety margin, such as `is_expired(delta=300)` to renew five minutes early.

### awscli (context manager)

`awscli()` yields `self`. On enter it removes `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, and `AWS_PROFILE` from `os.environ`, sets `AWS_REGION = self.aws_region`, then sets:

- `AWS_PROFILE`, if the manager was created with `profile_name`;
- otherwise `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`, plus `AWS_SESSION_TOKEN` when the credentials have a token (assumed roles).

On exit every one of these variables is restored to its value before the block, or removed if it was unset. Changes `os.environ` of the current process, so it is not thread-safe.

```python
import subprocess
with bsm.awscli():
    subprocess.run(["aws", "s3", "ls"])
```

### Snapshots

- `to_snapshot() -> dict`: `{"region_name", "aws_access_key_id", "aws_secret_access_key"}` plus `"aws_session_token"` when present. Resolves the current credentials, so a profile becomes plain keys. Contains secrets: do not log it.
- `from_snapshot(snapshot: dict) -> BotoSesManager` (classmethod): `cls(**snapshot)`.
- `from_snapshot_file(path: str | Path | None = PATH_DEFAULT_SNAPSHOT) -> BotoSesManager` (classmethod): reads the JSON file; raises `FileNotFoundError` if missing.
- `temp_snapshot(path: str | Path | None = PATH_DEFAULT_SNAPSHOT)` (context manager, yields `self`): writes `to_snapshot()` as JSON to `path`, deletes the file on exit.

Why `temp_snapshot` exists: inside another manager's `awscli()` block the environment points at a different account, so child processes lose the original session. A snapshot written first lets them recover it.

```python
bsm_a = BotoSesManager()
bsm_b = BotoSesManager(profile_name="acc_b")
with bsm_a.temp_snapshot():
    with bsm_b.awscli():
        subprocess.run(["aws", "sts", "get-caller-identity"])  # account B
        subprocess.run(["python", "child.py"])
        # in child.py: bsm_origin = BotoSesManager.from_snapshot_file()  -> account A
```

### clear_cache

`clear_cache() -> None`: drops the cached session, all clients and resources, and every identity and region value. The next access rebuilds them from the constructor arguments.

## AwsServiceEnum

A plain class of string constants, one per boto3 service id (430+), generated from the boto3 docs. Attribute names are the boto3 client class names, so they do not always match the id:

```python
AwsServiceEnum.S3 == "s3"
AwsServiceEnum.DynamoDB == "dynamodb"
AwsServiceEnum.Lambda == "lambda"
AwsServiceEnum.ACMPCA == "acm-pca"
AwsServiceEnum.PrometheusService == "amp"      # property: bsm.prometheusservice_client
```

Use with `get_client` / `get_resource`, or anywhere a boto3 service name string is expected.

## PATH_DEFAULT_SNAPSHOT

`pathlib.Path` to `~/.bsm-snapshot.json`, the default for `temp_snapshot` and `from_snapshot_file`. `None` on systems without a home directory, in which case those methods raise `EnvironmentError` unless `path` is passed.

## NoBotocoreCredentialError

`class NoBotocoreCredentialError(Exception)`: raised by `assume_role(auto_refresh=True)` when `boto_ses._session.get_credentials()` returns `None`, meaning the source session found no credentials.
