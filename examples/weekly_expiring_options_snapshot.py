import argparse
import logging
from ibapi.contract import Contract
from ib_tws_server.gen.client_responses import *
from ib_tws_server.gen.asyncio_client import *
from ib_tws_server.util.object_to_json import object_to_pretty_json

logger = logging.getLogger()
ib_client:AsyncioClient = None
symbol:str = None
expiration:str = None

def contract_for_symbol(sym: str):
    c = Contract()
    c.symbol = sym
    c.secType = "STK"
    c.currency = "USD"
    c.exchange = "SMART"
    return c

def option_contract_for_symbol(sym: str, strike: float, expiration: str, right: str):
    c = Contract()
    c.symbol = sym
    c.secType = "OPT"
    c.currency = "USD"
    c.exchange = "SMART"
    c.strike = strike
    c.lastTradeDateOrContractMonth = expiration
    c.right = right
    c.multiplier = "100"
    return c

async def code_for_symbol():
    details = await ib_client.reqContractDetails(contract_for_symbol(symbol))
    if len(details) > 1:
        raise RuntimeError(f"Ambiguous symbol {symbol}")
    return details[0].contract.conId

async def get_contract_details(exp: str, s: float):
    option_contract = option_contract_for_symbol(symbol, s, exp, "C")
    try:
        res = await ib_client.reqContractDetails(option_contract)
        option_contract = res[0].contract
    except IbError as e:
        print(f"Error getting contract for {exp} {s} {e}")
        return

    try:
        res = await ib_client.reqMktData(option_contract, "", False, False)
        print(object_to_pretty_json(res))
    except IbError as e:
        print(f"Error getting market data for {exp} {s}")
        return

async def main_loop():
    # Fill in contract code, this is required for reqSecDefOptParams
    code = await code_for_symbol()
    c = contract_for_symbol(symbol)
    c.conId = code

    res = await ib_client.reqSecDefOptParams(c.symbol, "", c.secType, c.conId)
    smart_exchange = None
    for l in res:
        if l.exchange == "SMART":
            smart_exchange = l
    if smart_exchange is None:
        raise RuntimeError(f"Entry for SMART exchange not found for {symbol}")

    reqs = []
    if expiration not in smart_exchange.expirations:
        raise RuntimeError(f"{symbol} does not have option contracts expiring {expiration}")
    for s in smart_exchange.strikes:
        reqs.append(get_contract_details(expiration, s))

    await asyncio.gather(*reqs, return_exceptions=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Print all option contracts and their latest bid/ask prices for a symbol")
    parser.add_argument("--port", "-p", dest='port', type=int, help="TWS port", default=7496)
    parser.add_argument("--host", "-t", dest='host', help="TWS host", default="127.0.0.1")
    parser.add_argument("--client-id", "-c", dest='client_id', help="TWS client id", default=0)
    parser.add_argument("--debug", "-d", dest='debug', action="store_true", help="Enable debug logging", default=False)
    parser.add_argument('--symbol', '-s', dest="symbol", required=True, help='The symbol')
    parser.add_argument('--expiration', '-e', dest="expiration", required=True, help='The expiration date')
    args  = parser.parse_args()
    symbol = args.symbol
    expiration = args.expiration

    ib_client = AsyncioClient()
    ib_client.start(args.host, args.port, args.client_id)

    asyncio.run(main_loop())
    ib_client.disconnect(True)
