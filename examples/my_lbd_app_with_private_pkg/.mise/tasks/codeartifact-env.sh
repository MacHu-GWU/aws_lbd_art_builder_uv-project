# Source this file in any mise task that needs to authenticate with AWS CodeArtifact.
# It sets UV_INDEX_ESC_USERNAME and UV_INDEX_ESC_PASSWORD so uv can resolve private packages.
# Configuration variables (profile, domain, owner, repo) are defined in mise.toml [env].
# Using --profile avoids polluting AWS_PROFILE in the environment.
# Token is valid for 12 hours (AWS default).
export UV_INDEX_ESC_USERNAME=aws

# In CI (GitHub Actions sets CI=true), credentials come from environment variables
# injected by aws-actions/configure-aws-credentials. No named profile exists.
# Locally, use the named AWS profile defined in AWS_CODEARTIFACT_PROFILE.
if [ -n "${CI:-}" ]; then
  PROFILE_FLAG=""
else
  PROFILE_FLAG="--profile $AWS_CODEARTIFACT_PROFILE"
fi

export UV_INDEX_ESC_PASSWORD=$(aws codeartifact get-authorization-token \
  $PROFILE_FLAG \
  --domain $AWS_CODEARTIFACT_DOMAIN \
  --domain-owner $AWS_CODEARTIFACT_DOMAIN_OWNER \
  --query authorizationToken \
  --output text)
