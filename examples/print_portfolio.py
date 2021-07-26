import argparse
import json
from ib_wrapper.gen.ib_client_responses import *
from ib_wrapper.gen.ib_asyncio_client import *


class JsonEncoder(json.JSONEncoder):
    def default(self, o):
        return o.__dict__

async def main_loop(c: IBAsyncioClient):
    p = await c.reqPositions()
    print(json.dumps(p, cls=JsonEncoder, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Output the current positions in JSON from TWS")
    parser.add_argument("--port", "-p", dest='port', type=int, help="TWS port", default=7496)
    parser.add_argument("--host", "-t", dest='host', help="TWS host", default="127.0.0.1")
    parser.add_argument("--client-id", "-c", dest='client_id', help="TWS client id", default=0)
    parser.add_argument("--debug", "-d", dest='debug', action="store_true", help="Enable debug logging", default=False)

    args = parser.parse_args()
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if args.debug else logging.INFO)
    logging.getLogger("ibapi").setLevel(level=logging.DEBUG if args.debug else logging.ERROR)

    c = IBAsyncioClient()
    c.start(args.host, args.port, args.client_id)

    asyncio.run(main_loop(c))

    c.disconnect()
