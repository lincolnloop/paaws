# Paaws

Paaws is an effort to build a PaaS on top of AWS.

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

### Paaws

### Application

An application consists of all the necessary AWS Resources to run. This is typically one or more Services, a Database, a Load Balancer, and multiple Parameters.

### Configuration

The resources associated with an Application are determined via a "sane" set of defaults which can be overridden via configuration in the Parameter Store.

#### Defaults

Paaws keys everything off the application name ("appname") by default.

* Cluster: `[appname]`
* Log Group: `[appname]`
* Parameter prefix: `/[appname]`
* Services & Tasks: anything running in cluster
* Interactive app shell: Creates a task from `[appname]-debug` Service defintion
* Database tasks: Tasks named `[appname]-dbutils-load`, `[appname]-dbutils-dump`, `[appname]-dbutils-shell`
* Database connection: in parameter store at `[prefix]/database_url`

#### Overrides

You can override the defaults by creating a parameter store key named `/paaws/apps/{appname}` with a JSON string in it containing any of the following keys:

* `cluster`
* `log_group`
* `parameter_prefix`
* `tags`
* `shell_service`

The `tags` value can be used to filter the set of Services and Tasks displayed from the Cluster. Keep in mind this is only a visual separation. IAM permissions are handled at the Cluster level, so no additional security is provided here.

Here is an example override from `/paaws/apps/ll-prod`:

```json
{
  "log_group": "/ecs/default/ll-prod",
  "cluster": "default",
  "tags": [
    {
      "key": "Application",
      "value": "lincolnloop"
    },
    {
      "key": "Environment",
      "value": "prod"
    }
  ],
  "shell_service": "ll-prod-web"
}
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

## Future Ideas

* Web interface
* Convert CLI to Go for easier distribution
