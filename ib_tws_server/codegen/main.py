import argparse
import ibapi
from ib_tws_server.codegen.asyncio_client_generator import AsyncioWrapperGenerator
from ib_tws_server.codegen import *
from ib_tws_server.api_definition import * 
import logging
import os
import shutil
import sys

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)

def generate(output_dir: str):
    response_class_fname = os.path.join(output_dir, "client_responses.py")
    asyncio_client_fname = os.path.join(output_dir, "asyncio_client.py")
    asyncio_wrapper_fname = os.path.join(output_dir, "asyncio_wrapper.py")
    graphql_schema_fname = os.path.join(output_dir, "schema.graphql")
    graphql_resolver_fname = os.path.join(output_dir, "graphql_resolver.py")

    shutil.rmtree(output_dir, ignore_errors=True)
    os.mkdir(output_dir)

    print(f"Generating code for TWS API Version {ibapi.get_version_string()}")

    d = ApiDefinition.verify()
    ResponseTypesGenerator.generate(response_class_fname)
    AsyncioClientGenerator.generate(asyncio_client_fname)
    AsyncioWrapperGenerator.generate(asyncio_wrapper_fname)
    GraphQLSchemaGenerator.generate(graphql_schema_fname)
    GraphQLResolverGenerator.generate(graphql_resolver_fname)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate wrapper classes from the request definitions")
    parser.add_argument('--output-dir', '-o', dest="output_dir", required=True, help='The output directory')
    args  = parser.parse_args()
    generate(args.output_dir)
