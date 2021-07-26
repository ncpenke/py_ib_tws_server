import argparse
from ib_wrapper.codegen.ib_asyncio_client_generator import IBAsyncioClientGenerator
from posixpath import pathsep
from ib_wrapper.codegen.ib_client_response_types_generator import *
from ib_wrapper.api_definition import *
import os

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate wrapper classes from the request definitions")
    parser.add_argument('--output-dir', '-o', dest="output_dir", required=True, help='The output directory')
    args  = parser.parse_args()

    response_class_fname = os.path.join(args.output_dir, "ib_client_responses.py")
    ib_asyncio_client_fname = os.path.join(args.output_dir, "ib_asyncio_client.py")

    os.mkdir(args.output_dir)

    d = ApiDefinitionManager()
    IBClientResponseTypeGenerator.generate(response_class_fname)
    IBAsyncioClientGenerator.generate(ib_asyncio_client_fname)
