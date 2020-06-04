import json
import datetime
from typing import List

import boto3

from ..utils import load_parameters


class PipelineNotFound(Exception):
    pass


def pipeline_list() -> dict:
    return load_parameters("/paaws/pipelines/")


def pipeline_detail(name: str) -> List[dict]:
    ssm = boto3.client("ssm")
    try:
        return json.loads(
            ssm.get_parameter(Name=f"/paaws/pipelines/{name}")["Parameter"]["Value"]
        )
    except ssm.exceptions.ParameterNotFound:
        raise PipelineNotFound


def pipeline_for_app(name: str) -> str:
    ssm = boto3.client("ssm")
    try:
        return json.loads(
            ssm.get_parameter(Name=f"/paaws/apps/{name}/pipeline")["Parameter"]["Value"]
        )["name"]
    except ssm.exceptions.ParameterNotFound:
        raise PipelineNotFound


def validate_promotion(source: str, dest: str) -> bool:
    source_pipeline = pipeline_for_app(source)
    dest_pipeline = pipeline_for_app(dest)
    if source_pipeline != dest_pipeline:
        raise RuntimeError(
            f"Source pipeline ({source_pipeline}) does not equal destination ({dest_pipeline})"
        )
    source_step = -1
    dest_step = -1
    for idx, stage in enumerate(pipeline_detail(source_pipeline)):
        if stage["app"] == source:
            source_step = idx
        elif stage["app"] == dest:
            dest_step = idx
    if source_step >= dest_step:
        raise RuntimeError("Destination app is not downstream from source app")
    return True


def promote(
    source_name: str,
    source_build_number: int,
    source_build_id: str,
    source_commit: str,
    dest: str,
) -> None:
    validate_promotion(source=source_name, dest=dest)
    ssm = boto3.client("ssm")
    ssm.put_parameter(
        Name=f"/paaws/apps/{dest}/pipeline/promoted",
        Overwrite=True,
        Type="String",
        Value=json.dumps(
            {
                "source": source_name,
                "build_number": source_build_number,
                "build_id": source_build_id,
                "commit": source_commit,
                "started": datetime.datetime.utcnow().isoformat(),
            }
        ),
    )
