# coding=utf-8
# ------------------------------------
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
# ------------------------------------

import functools
import uuid
from devtools_testutils import set_bodiless_matcher, get_credential
from devtools_testutils.aio import recorded_by_proxy_async
from azure.ai.documentintelligence.aio import DocumentIntelligenceAdministrationClient, DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    ClassifierDocumentTypeDetails,
    AzureBlobContentSource,
    BuildDocumentClassifierRequest,
    ClassifyDocumentRequest,
)
from asynctestcase import AsyncDocumentIntelligenceTest
from conftest import skip_flaky_test
from preparers import DocumentIntelligencePreparer, GlobalClientPreparerAsync as _GlobalClientPreparer


DocumentModelAdministrationClientPreparer = functools.partial(
    _GlobalClientPreparer, DocumentIntelligenceAdministrationClient
)


class TestDACClassifyDocumentAsync(AsyncDocumentIntelligenceTest):
    @skip_flaky_test
    @DocumentIntelligencePreparer()
    @recorded_by_proxy_async
    async def test_classify_document(self, documentintelligence_training_data_classifier_sas_url, **kwargs):
        set_bodiless_matcher()
        documentintelligence_endpoint = kwargs.pop("documentintelligence_endpoint")
        di_client = DocumentIntelligenceClient(documentintelligence_endpoint, get_credential(is_async=True))
        di_admin_client = DocumentIntelligenceAdministrationClient(
            documentintelligence_endpoint, get_credential(is_async=True)
        )

        recorded_variables = kwargs.pop("variables", {})
        recorded_variables.setdefault("classifier_id", str(uuid.uuid4()))

        request = BuildDocumentClassifierRequest(
            classifier_id=recorded_variables.get("classifier_id"),
            doc_types={
                "IRS-1040-A": ClassifierDocumentTypeDetails(
                    azure_blob_source=AzureBlobContentSource(
                        container_url=documentintelligence_training_data_classifier_sas_url, prefix="IRS-1040-A/train"
                    )
                ),
                "IRS-1040-B": ClassifierDocumentTypeDetails(
                    azure_blob_source=AzureBlobContentSource(
                        container_url=documentintelligence_training_data_classifier_sas_url, prefix="IRS-1040-B/train"
                    )
                ),
                "IRS-1040-C": ClassifierDocumentTypeDetails(
                    azure_blob_source=AzureBlobContentSource(
                        container_url=documentintelligence_training_data_classifier_sas_url, prefix="IRS-1040-C/train"
                    )
                ),
            },
        )
        async with di_admin_client:
            poller = await di_admin_client.begin_build_classifier(request)
            classifier = await poller.result()
        # FIXME: Tracking issue: https://github.com/Azure/azure-sdk-for-python/issues/38881
        # assert classifier.classifier_id == recorded_variables.get("classifier_id")
        assert len(classifier.doc_types) == 3

        with open(self.irs_classifier_document, "rb") as fd:
            my_file = fd.read()

        async with di_client:
            # Test classifying document from local
            poller = await di_client.begin_classify_document(
                classifier.classifier_id,
                my_file,
            )
            document = await poller.result()
            assert document.model_id == classifier.classifier_id
            assert len(document.pages) == 4
            assert document.tables is None
            assert document.paragraphs is None
            assert document.styles is None
            assert document.string_index_type == "textElements"
            assert document.content_format == "text"

            # Test classifying document from remote
            poller = await di_client.begin_classify_document(
                classifier.classifier_id,
                ClassifyDocumentRequest(url_source=self.irs_classifier_document_url),
            )
            document_from_url = await poller.result()
            assert document_from_url.model_id == document.model_id
            assert document_from_url.pages == document.pages
            assert document_from_url.tables == document.tables
            assert document_from_url.paragraphs == document.paragraphs
            assert document_from_url.styles == document.styles
            assert document_from_url.string_index_type == document.string_index_type
            assert document_from_url.content_format == document.content_format

        return recorded_variables
