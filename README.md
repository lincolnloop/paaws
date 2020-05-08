# Paaws

[![Build](https://github.com/lincolnloop/paaws/workflows/Build/badge.svg)](https://github.com/lincolnloop/paaws/actions?query=workflow%3ABuild)

Paaws is **a CLI that makes AWS services feel more like a PaaS** such as [Heroku](https://www.heroku.com/) or [Dokku](http://dokku.viewdocs.io/dokku/). It is designed to work with:

* [Elastic Container Service (ECS)](https://aws.amazon.com/ecs/) for running the application process(es)
* [Parameter Store](https://aws.amazon.com/systems-manager/features/#Parameter_Store) for environment variable/secret storage
* [Cloudwatch Logs](https://aws.amazon.com/cloudwatch/features/) for logging
* [Session Manager](https://aws.amazon.com/systems-manager/features/#Session_Manager) for shell access
* [Codebuild](https://aws.amazon.com/codebuild/) for building images and testing


Paaws was created by [Lincoln Loop](https://lincolnloop.com) to help developers manage and monitor services running on AWS without needing deep knowledge of the AWS itself. We are currently using it manage services in production.

Internally we have created a Terraform module to spin up services using [Buildpacks](https://buildpacks.io/) and a [Procfile](https://devcenter.heroku.com/articles/procfile), allowing developers to run new applications on AWS with very little configuration. We hope to release this as a Terraform and/or Cloudformation module in the future. In the meantime, however, the CLI is designed to work with existing systems via some configuration stored in AWS' Parameter Store.

If you're interested in commercial support for Paaws, please [contact us](https://lincolnloop.com/contact/).

🚧 This is an early release and under active development. APIs and commands may change between releases.

## Installation

The CLI requires Python 3.6+. It can be installed via pip:

```
pip install paaws
```

Or you can download the most recent release from the [Releases](https://github.com/lincolnloop/paaws/releases) page and run it via `python3 paaws ...` or run `chmod +x paaws` and run it directly, `./paaws ...`.  


## Goals

1. **Developer friendly** Developers should be able to use the PaaS without being AWS experts. When in doubt, see how Heroku does it.
2. **Cloud native** Leverage AWS services wherever possible. Avoid running any additional services just to make the PaaS functional. No additional maintenance is required.
3. **Secure** Follows general best practice and is compatible with locked down IAM policies.

# Development

```
python -m venv .venv && . .venv/bin/activate
pip install flit
flit install --symlink --deps develop
```

In development, you can run the CLI with:
 
 ```
 python -m paaws ...
```

# Distribution

The app can be bundled into a Python zipapp with shiv: 

```
make paaws.pyz
```

## Terminology

### AWS

#### Task (ECS)

One or more containers that are usually run as part of a Service, but may be run as a one-off process, e.g. shell access, release process, etc.

#### Service (ECS)

A task that should run forever like a daemon process. Can be scaled up to run multiple instances.

#### Log Group (Cloudwatch)

Log storage/aggregation

#### Container Instance (ECS/EC2)

A virtual server that runs the Docker daemon which executes the Tasks. Each Instance is part of a single Cluster (see below)

#### Fargate (ECS)

An AWS managed Task runner that does not require running Container Instances.

#### Cluster (ECS)

All Tasks run within a Cluster which serves as both a logical and security boundary.

#### Parameter Store (SSM)

A set of key/value strings stored with or without encryption. Usually used to inject environment variables into Tasks. Keys use a path-style notation and permissions can include a wildcard, so often keys are defined as `/{application_name}/{key}` and permissions are granted on `/{application_name}/*`.

## Paaws

### Application

An application consists of all the necessary AWS Resources to run. This is typically one or more Services, a Database, a Load Balancer, and multiple Parameters.

### Configuration

The resources associated with an Application are determined via a "sane" set of defaults which can be overridden via configuration in the Parameter Store.

The default configuration is generated via the provided app name. If `my-app` were your app name, the configuration would be:

```json
{
  "cluster": {"name": "my-app"},
  "log_group": {"name": "my-app"},
  "parameter_store": {
      "prefix": "/my-app",
      "chamber_compatible": false
  },
  "codebuild_project": {"name": "my-app"},
  "shell": {
      "task_amily": "my-app-shell",
      "command": "bash -l"
  },
  "db_utils": {
      "shell_task_family": "my-app-dbutils-shell",
      "dumpload_task_family": "my-app-dbutils-dumpload",
      "s3_bucket": "myapp-dbutils"
  },
  "tags": []
}
```

The `tags` value can be used to filter the set of Services and Tasks displayed from the Cluster. Keep in mind this is only a visual separation. IAM permissions are handled at the Cluster level, so no additional security is provided here.

#### Overrides

You can override the defaults by creating a parameter store key named `/paaws/apps/{appname}/settings` with a JSON string in it. An example using the AWS CLI:

```
$ aws ssm put-parameter \
  --name /paaws/apps/$APPNAME/settings \
  --value '{"cluster": {"name": "default"}, "log_group": {"name": "/aws/ecs/default/my-app"}}' \
  --type String \
  --overwrite
```

## Available Commands

<!-- generate with `python -m paaws.docs` -->

### `builds`

View build information

* `list` List most recent builds
* `view` View status for a specific build
* `logs` View build or test logs for a specific build

### `config`

View/edit environment variables

* `list` Environment variables for applications
* `get` Get the value for a variable
* `set` Get the value for a variable
* `unset` Unset (delete) a variable

### `db`

Perform database tasks

* `dump` Dump database to local file
* `load` Replace remote database with local dump
* `shell` Run an interactive database shell

### `deployments`

List deployments

### `logs`

View application logs

* `view` Show application logs
* `console` Open logs in web console

### `ps`

Show running containers

### `shell`

Open an interactive shell in the remote environment


## Thanks

Paaws is the result of a few years of learning while working with clients hosting applications on ECS. The Paaws CLI was born out of work we've been doing with [Wharton Interactive](https://interactive.wharton.upenn.edu/) and received their blessing to continue as an independent open source project. Thanks Sarah! 🎉
