import json
import os
from tempfile import NamedTemporaryFile
from typing import Any, List

from google.cloud import storage
from google.cloud.storage import Client
from obsei.payload import TextPayload
from obsei.sink.base_sink import BaseSinkConfig, Convertor, BaseSink
from obsei.source.playstore_scrapper import PlayStoreScrapperConfig, PlayStoreScrapperSource



class GCSSinkConfig(BaseSinkConfig):
    key_env_var: str = "GENAI_GCP_CREDENTIALS"
    bucket_name: str
    blob: str
    tag: str

    def __init__(self, **data: Any):
        super().__init__(**data)
        with NamedTemporaryFile() as tmp:
            tmp.write(os.environ[self.key_env_var].encode())
            tmp.flush()
            self._client = storage.Client.from_service_account_json(tmp.name)

    def get_gcs_client(self) -> Client:
        return self._client

    def upload_json_to_gcs(self, data) -> None:
        bucket = self._client.get_bucket(self.bucket_name)
        blob = bucket.blob(self.blob)
        blob.upload_from_string(json.dumps(data), content_type="application/json")


class GCSSink(BaseSink):
    def __init__(self, convertor: Convertor = Convertor(), **data: Any):
        super().__init__(convertor=convertor, **data)

    def send_data(  # type: ignore[override]
        self,
        analyzer_responses: List[TextPayload],
        config: GCSSinkConfig,
        **kwargs: Any,
    ) -> Any:
        payloads = []
        for analyzer_response in analyzer_responses:
            payloads.append(
                self.convertor.convert(
                    analyzer_response=analyzer_response,
                    base_payload={
                        "tag": config.tag,
                    }
                )
            )

        config.upload_json_to_gcs(data=payloads)


# initialize play store source config
source_config = PlayStoreScrapperConfig(
   # Need two parameters package_name and country.
   # `package_name` can be found at the end of the url of app in play store.
   # For example - https://play.google.com/store/apps/details?id=com.google.android.gm&hl=en&gl=US
   # `com.google.android.gm` is the package_name for xcode and `us` is country.
   countries=["in"],
   package_name="com.chess",
   # max_count=10000, # Number of reviews to fetch
   lookup_period="90d"  # Lookup period from current time, format: `<number><d|h|m>` (day|hour|minute)
)

# initialize play store reviews retriever
source = PlayStoreScrapperSource()

# Initialize Analyzer based on workflow
# analyzer = obsei_configuration.initialize_instance("analyzer")
# analyzer_config = obsei_configuration.initialize_instance("analyzer_config")

# Initialize Informer based on workflow
sink_config = GCSSinkConfig(bucket_name="startup-experiments-public-data",
                            blob="app-store-reviews/chess.json", tag="chess")
sink = GCSSink()

# Execute Observer to fetch result
source_response_list = source.lookup(source_config)

# Execute Analyzer to perform analysis on Observer's output with given analyzer config
# analyzer_response_list = analyzer.analyze_input(
#      source_response_list=source_response_list, analyzer_config=analyzer_config
# )

# Send analyzed result to Informer
sink_response_list = sink.send_data(source_response_list, sink_config)
