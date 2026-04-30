"""Batch use-case: format metadata for CLI output."""

import json
from dataclasses import dataclass
from typing import Union

from photowalk.catalog import MediaCatalog
from photowalk.formatters import format_csv, format_table
from photowalk.models import PhotoMetadata, VideoMetadata


@dataclass(frozen=True)
class BatchResult:
    results: list[Union[PhotoMetadata, VideoMetadata]]
    formatted_output: str
    output_format: str


class BatchUseCase:
    def run(self, catalog: MediaCatalog, output_format: str) -> BatchResult:
        results = [meta for _, meta in catalog.pairs]
        if output_format == "json":
            formatted = json.dumps([r.to_dict() for r in results], indent=2)
        elif output_format == "csv":
            formatted = format_csv(results)
        else:
            formatted = format_table(results)
        return BatchResult(
            results=results,
            formatted_output=formatted,
            output_format=output_format,
        )
