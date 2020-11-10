# Copyright 2019 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#            http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
`compute.py`
Compute utilities.
"""

import logging
import pprint
import time

from slo_generator import utils
from slo_generator.report import SLOReport

LOGGER = logging.getLogger(__name__)


def compute(slo_config,
            error_budget_policy,
            timestamp=None,
            client=None,
            do_export=False,
            delete=False):
    """Run pipeline to compute SLO, Error Budget and Burn Rate, and export the
    results (if exporters are specified in the SLO config).

    Args:
        slo_config (dict): SLO configuration.
        error_budget_policy (dict): Error Budget policy configuration.
        timestamp (int, optional): UNIX timestamp. Defaults to now.
        client (obj, optional): Existing metrics backend client.
        do_export (bool, optional): Enable / Disable export. Default: False.
        delete (bool, optional): Enable / Disable delete mode. Default: False.
    """
    start = time.time()
    if timestamp is None:
        timestamp = time.time()

    # Compute SLO, Error Budget, Burn rates and make report
    exporters = slo_config.get('exporters')
    reports = []
    for step in error_budget_policy:
        report = SLOReport(config=slo_config,
                           step=step,
                           timestamp=timestamp,
                           client=client,
                           delete=delete)

        if not report.valid:
            continue

        if delete:  # delete mode is enabled
            continue

        LOGGER.info(report)
        json_report = report.to_json()

        if exporters is not None and do_export is True:
            responses = export(json_report, exporters)
            json_report['exporters'] = responses
        reports.append(json_report)
    end = time.time()
    run_duration = round(end - start, 1)
    LOGGER.debug(pprint.pformat(reports))
    LOGGER.debug(f'Run finished successfully in {run_duration}s.')
    return reports


def export(data, exporters, raise_on_error=False):
    """Export data using selected exporters.

    Args:
        data (dict): Data to export.
        exporters (list): List of exporter configurations.

    Returns:
        obj: Return values from exporters output.
    """
    LOGGER.debug(f'Exporters: {pprint.pformat(exporters)}')
    LOGGER.debug(f'Data: {pprint.pformat(data)}')
    responses = []

    # Passing one exporter as a dict will work for convenience
    if isinstance(exporters, dict):
        exporters = [exporters]

    for config in exporters:
        try:
            exporter_class = config.get('class')
            LOGGER.info(f'Exporting results to {exporter_class}')
            LOGGER.debug(f'Exporter config: {pprint.pformat(config)}')
            exporter = utils.get_exporter_cls(exporter_class)()
            response = exporter.export(data, **config)
            if isinstance(response, list):
                for elem in response:
                    elem['exporter'] = exporter_class
            responses.append(response)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.critical(exc, exc_info=True)
            LOGGER.error(f'{exporter_class}Exporter failed. Passing.')
            if raise_on_error:
                raise exc
            responses.append(exc)
    return responses
