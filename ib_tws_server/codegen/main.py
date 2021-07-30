import argparse
from ib_tws_server.codegen import *
from ib_tws_server.api_definition import *
import os

logger = logging.getLogger()
logger.setLevel(logging.ERROR)
logging.basicConfig(stream=sys.stdout)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate wrapper classes from the request definitions")
    parser.add_argument('--output-dir', '-o', dest="output_dir", required=True, help='The output directory')
    args  = parser.parse_args()

    response_class_fname = os.path.join(args.output_dir, "client_responses.py")
    ib_asyncio_client_fname = os.path.join(args.output_dir, "ib_asyncio_client.py")
    graphql_schema_fname = os.path.join(args.output_dir, "schema.graphql")

    os.mkdir(args.output_dir)

    d = ApiDefinitionManager()
    ResponseTypesGenerator.generate(response_class_fname)
    IBAsyncioClientGenerator.generate(ib_asyncio_client_fname)
    GraphQLSchemaGenerator.generate(graphql_schema_fname)
