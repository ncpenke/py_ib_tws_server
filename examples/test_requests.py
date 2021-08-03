import argparse
from datetime import datetime, timedelta
import json
import logging
from ibapi import contract
from ibapi.contract import Contract
from ib_tws_server.asyncio.error import Error
from ib_tws_server.gen.client_responses import *
from ib_tws_server.gen.asyncio_client import *
from typing import Awaitable, Type

logger = logging.getLogger()

class JsonEncoder(json.JSONEncoder):
    """
    Default JSON encoder to debug responses
    """
    def default(self, o):
        return o.__dict__

def contract_for_symbol(sym: str):
    c = Contract()
    c.symbol = sym
    c.secType = "STK"
    c.currency = "USD"
    c.exchange = "SMART"
    return c

def option_for_symbol(sym: str, strike: float):
    c = Contract()
    c.symbol = sym
    c.secType = "OPT"
    c.currency = "USD"
    c.exchange = "SMART"
    c.lastTradeDateOrContractMonth = "20210820"
    c.strike = 3300
    c.right = "C"
    c.multiplier = "100"
    return c

def log_result(p: bool, res: any, req: any):
    if (p):
        logger.log(logging.INFO, f"SUCCESS {req.__name__} returned {res.__class__.__name__}")
    else:
        if isinstance(res, Error):
            err: Error = res
            logger.log(logging.INFO, f"FAILED  {req.__name__} returned Error reason: {err.reason} code: {err.code}")
        else:
            logger.log(logging.INFO, f"FAILED  {req.__name__} returned {res.__class__.__name__}")

async def test_async_request(test: Awaitable, check_response: Callable[[object],bool]):
    res = await test
    logger.log(logging.DEBUG, json.dumps(res, cls=JsonEncoder, indent="  "))
    log_result(check_response(res), res, test)

class StreamingCallback:
    _future: asyncio.Future
    _check_response: Callable[[object],bool]
    _res: object
    _loop: asyncio.AbstractEventLoop

    def __init__(self, check_response: Callable[[object],bool]):
        self._loop = asyncio.get_running_loop()
        self._future = asyncio.get_running_loop().create_future()
        self._check_response = check_response

    def __call__(self, res):
        if self._future is not None:
            self._future.set_result(res)
        self._future = None

    async def wait_for_result(self) -> bool:
        self._res = await self._future
        return self._check_response(self._res)

    def res(self):
        return self._res

async def test_streaming_request(test: Callable, check_response: Callable, *args):
    fail: bool = False
    cb = StreamingCallback(check_response)
    sub: Subscription = await test(cb, *args)

    if sub is None:
        log_result(False, test, test)
        return

    res = await cb.wait_for_result()
    log_result(res, cb.res(), test)

    sub.cancel()

async def main_loop(c: AsyncioClient):
    await asyncio.gather(
        test_async_request(c.reqCurrentTime(), lambda c: c is not None and c.currentTime.time > 0),
        test_async_request(c.reqPositions(), lambda c: c is not None and isinstance(c, list)),
        test_async_request(c.reqManagedAccts(), lambda c: c is not None and len(c.managedAccounts.accountsList) > 0),
        test_async_request(c.reqFundamentalData(contract_for_symbol("AMZN"), "ReportSnapshot", None), lambda c: True),
        test_async_request(c.reqHistoricalData(contract_for_symbol("AMZN"), "", "60 S", "1 secs", "TRADES", 0, 2, "XYZ"), lambda c: c is not None and isinstance(c, list)),
        test_async_request(c.reqContractDetails(option_for_symbol("AMZN", 3300)), lambda x: x is not None and isinstance(x, list)),
        test_streaming_request(c.reqTickByTickData, lambda c: c is not None and isinstance(c, ReqTickByTickDataUpdate), contract_for_symbol("AMZN"), "BidAsk", 0, False),
        test_streaming_request(c.reqHistoricalDataAsSubscription, lambda c: c is not None and isinstance(c, ReqHistoricalDataUpdate), contract_for_symbol("U"), "", "60 S", "1 secs", "TRADES", 0, 2, "XYZ")
    )

    if c.active_request_count() > 0:
        logger.error(f"{c.active_request_count()} requests still active")
    if c.active_subscription_count() > 0:
        logger.error(f"{c.active_subscription_count()} subscriptions still active")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Output the current positions in JSON from TWS")
    parser.add_argument("--port", "-p", dest='port', type=int, help="TWS port", default=7496)
    parser.add_argument("--host", "-t", dest='host', help="TWS host", default="127.0.0.1")
    parser.add_argument("--client-id", "-c", dest='client_id', help="TWS client id", default=0)
    parser.add_argument("--debug", "-d", dest='debug', action="store_true", help="Enable debug logging", default=False)

    args = parser.parse_args()
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if args.debug else logging.INFO)
    logging.getLogger("ibapi").setLevel(level=logging.DEBUG if args.debug else logging.ERROR)

    c = AsyncioClient()
    c.start(args.host, args.port, args.client_id)

    asyncio.run(main_loop(c))

    c.disconnect(True)
