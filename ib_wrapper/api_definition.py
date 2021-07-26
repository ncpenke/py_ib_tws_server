from ibapi.client import EClient
from ibapi.wrapper import EWrapper
import inspect
import logging
from typing import Callable, Dict, List, MutableSet, Tuple

logger = logging.getLogger(__name__)

class ApiDefinition:
    request_method: Callable = None
    cancel_method: Callable = None
    update_methods: List[Callable] = None
    stream_methods: List[Callable] = None
    done_method: Callable = None
    req_id_names: List[str] = None
    has_done_flag: bool = False

    def __init__(self, request_method: Callable, 
        cancel_method: Callable = None, 
        update_methods: List[Callable] = None, 
        done_method: Callable = None, 
        req_id_names: List[str] = None, 
        stream_methods: List[Callable] = None,
        has_done_flag: bool = False):
        self.request_method = request_method
        self.cancel_method = cancel_method
        self.update_methods = update_methods
        self.done_method = done_method
        self.req_id_names = req_id_names
        self.stream_methods = stream_methods
        self.has_done_flag = has_done_flag

class ApiDefinitionManager:
    def __init__(self):
        for d in ApiDefinitionManager.DEFINITIONS: self.flag_request_definition(d)
        self.log_unprocessed_methods()
        self._unknown_requests: MutableSet[str] = set()
        self._req_members: Dict[str, object] = {}
        self._res_members: Dict[str, object] = {}

    def process_request_definition(self, name: str, type: object):
        if  not name.startswith("req"):
            return
        data_type = name[3:]
        definition = ApiDefinition( 
            request_method=type,
            cancel_method=self.find_cancel_method(data_type),
            done_method=self.find_done_method(data_type), 
            req_id_names=self.get_req_id_parameter(type),
            update_methods=self.find_update_methods(data_type))
        self.flag_request_definition(definition)

    def log_unprocessed_methods(self):
        predicate = lambda x: inspect.isfunction(x) and not inspect.isbuiltin(x) and not inspect.ismethoddescriptor(x) and not x.__name__.startswith("__")
        for name,type in inspect.getmembers(EClient, predicate): 
            if not name in self.IGNORE_NAMES:
                logger.error(f"Unhandled request: {name}")
        for name,type in inspect.getmembers(EWrapper, predicate):
            if not name in self.IGNORE_NAMES:
                logger.error(f"Unhandled response: {name}")

    def flag_request_definition(self, definition: ApiDefinition):
        if (definition.request_method is not None):
            self.IGNORE_NAMES.add(definition.request_method.__name__)
        if (definition.cancel_method is not None):
            self.IGNORE_NAMES.add(definition.cancel_method.__name__)
        if (definition.update_methods is not None):
            for m in definition.update_methods: 
                self.IGNORE_NAMES.add(m.__name__)
        if (definition.stream_methods is not None):
            for m in definition.stream_methods: 
                self.IGNORE_NAMES.add(m.__name__)
        if (definition.done_method is not None):
            self.IGNORE_NAMES.add(definition.done_method.__name__)

    IGNORE_NAMES: MutableSet[str] = set({
        "connect",
        "connectAck",
        "connectionClosed",
        "disconnect",
        "error",
        "isConnected",
        "keyboardInterrupt",
        "keyboardInterruptHard",
        "logAnswer",
        "logRequest",
        "msgLoopRec",
        "msgLoopTmo",
        "reset",
        "run",
        "sendMsg",
        "serverVersion",
        "setConnState",
        "setConnectionOptions",
        "startApi",
        "twsConnectionTime",
        "verifyAndAuthCompleted",
        "verifyAndAuthMessage",
        "verifyAndAuthMessageAPI",
        "verifyAndAuthRequest",
        "verifyCompleted",
        "verifyMessage",
        "verifyMessageAPI",
        "verifyRequest",
        "winError"
    })

    DEFINITIONS: List[ApiDefinition] = [
        ApiDefinition(request_method=EClient.queryDisplayGroups, 
            update_methods=[EWrapper.displayGroupList],
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.exerciseOptions, req_id_names= "reqId"),
        ApiDefinition(request_method=EClient.calculateImpliedVolatility, 
            stream_methods=[EWrapper.tickOptionComputation],
            cancel_method=EClient.cancelCalculateImpliedVolatility,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.calculateOptionPrice, 
            stream_methods=[EWrapper.tickOptionComputation],
            cancel_method=EClient.cancelCalculateOptionPrice,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqAccountSummary, 
            update_methods=[EWrapper.accountSummary],
            cancel_method=EClient.cancelAccountSummary,
            done_method=EWrapper.accountSummaryEnd,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqAccountUpdatesMulti, 
            update_methods=[EWrapper.accountUpdateMulti],
            cancel_method=EClient.cancelAccountUpdatesMulti,
            done_method=EWrapper.accountUpdateMultiEnd,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqFundamentalData, 
            update_methods=[EWrapper.fundamentalData],
            cancel_method=EClient.cancelFundamentalData,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqHeadTimeStamp, 
            update_methods=[EWrapper.headTimestamp],
            cancel_method=EClient.cancelHeadTimeStamp,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqHistogramData, 
            update_methods=[EWrapper.histogramData],
            cancel_method=EClient.cancelHistogramData,
            req_id_names=["reqId","tickerId"]),
        ApiDefinition(request_method=EClient.reqHistoricalData, 
            update_methods=[EWrapper.historicalData],
            stream_methods=[EWrapper.historicalDataUpdate],
            cancel_method=EClient.cancelHistoricalData,
            done_method=EWrapper.historicalDataEnd,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqMktData, 
            stream_methods=[EWrapper.tickPrice, EWrapper.tickSize, 
                EWrapper.tickEFP, EWrapper.tickGeneric, 
                EWrapper.tickNews, EWrapper.rerouteMktDataReq, 
                EWrapper.rerouteMktDepthReq, EWrapper.tickReqParams, 
                EWrapper.tickString, EWrapper.deltaNeutralValidation],
            cancel_method=EClient.cancelMktData,
            done_method=EWrapper.tickSnapshotEnd,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqMktDepth, 
            stream_methods=[EWrapper.updateMktDepth, EWrapper.updateMktDepthL2],
            cancel_method=EClient.cancelMktDepth,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqNewsBulletins,
            stream_methods=[EWrapper.updateNewsBulletin],
            cancel_method=EClient.cancelNewsBulletins,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.placeOrder,
            stream_methods=[EWrapper.orderStatus],
            cancel_method=EClient.cancelOrder),
        ApiDefinition(request_method=EClient.reqPnL,
            update_methods=[EWrapper.pnl],
            cancel_method=EClient.cancelPnL,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqPnLSingle,
            update_methods=[EWrapper.pnlSingle],
            cancel_method=EClient.cancelPnLSingle,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqPositions,
            update_methods=[EWrapper.position],
            done_method=EWrapper.positionEnd,
            cancel_method=EClient.cancelPositions),
        ApiDefinition(request_method=EClient.reqPositionsMulti,
            update_methods=[EWrapper.positionMulti],
            done_method=EWrapper.positionMultiEnd,
            cancel_method=EClient.cancelPositionsMulti,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqRealTimeBars,
            stream_methods=[EWrapper.realtimeBar],
            cancel_method=EClient.cancelRealTimeBars,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqScannerSubscription,
            update_methods=[EWrapper.scannerData],
            done_method=EWrapper.scannerDataEnd,
            cancel_method=EClient.cancelScannerSubscription,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqTickByTickData,
            stream_methods=[EWrapper.tickByTickAllLast, EWrapper.tickByTickBidAsk, EWrapper.tickByTickMidPoint],
            cancel_method=EClient.cancelTickByTickData,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.replaceFA,
            done_method=EWrapper.replaceFAEnd,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqAccountUpdates,
            update_methods=[EWrapper.updateAccountValue, EWrapper.updateAccountTime, EWrapper.updatePortfolio],
            done_method=EWrapper.accountDownloadEnd),
        ApiDefinition(request_method=EClient.reqOpenOrders,
            stream_methods=[EWrapper.orderStatus,EWrapper.openOrder],
            done_method=EWrapper.openOrderEnd),
        ApiDefinition(request_method=EClient.reqAllOpenOrders,
            stream_methods=[EWrapper.orderStatus,EWrapper.openOrder],
            done_method=EWrapper.openOrderEnd),
        ApiDefinition(request_method=EClient.reqAutoOpenOrders,
            stream_methods=[EWrapper.orderStatus,EWrapper.openOrder],
            done_method=EWrapper.openOrderEnd),
        ApiDefinition(request_method=EClient.reqContractDetails,
            update_methods=[EWrapper.contractDetails,EWrapper.bondContractDetails],
            done_method=EWrapper.contractDetailsEnd,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqCurrentTime,
            update_methods=[EWrapper.currentTime]),
        ApiDefinition(request_method=EClient.reqCompletedOrders,
            update_methods=[EWrapper.completedOrder],
            done_method=EWrapper.completedOrdersEnd),
        ApiDefinition(request_method=EClient.reqExecutions,
            update_methods=[EWrapper.execDetails],
            done_method=EWrapper.execDetailsEnd,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqFamilyCodes,
            update_methods=[EWrapper.familyCodes]),
        ApiDefinition(request_method=EClient.reqGlobalCancel),
        ApiDefinition(request_method=EClient.reqHistoricalNews,
            update_methods=[EWrapper.historicalNews],
            done_method=EWrapper.historicalNewsEnd,
            req_id_names=["requestId","reqId"]),
        ApiDefinition(request_method=EClient.reqHistoricalTicks,
            update_methods=[EWrapper.historicalTicks, EWrapper.historicalTicksBidAsk, EWrapper.historicalTicksLast],
            req_id_names=["reqId"],
            has_done_flag=True),
        ApiDefinition(request_method=EClient.reqIds,
            update_methods=[EWrapper.nextValidId]),
        ApiDefinition(request_method=EClient.reqManagedAccts,
            update_methods=[EWrapper.managedAccounts]),
        ApiDefinition(request_method=EClient.reqMarketDataType,
            stream_methods=[EWrapper.marketDataType]),
        ApiDefinition(request_method=EClient.reqMarketRule,
            update_methods=[EWrapper.marketRule]),
        ApiDefinition(request_method=EClient.reqMatchingSymbols,
            update_methods=[EWrapper.symbolSamples]),
        ApiDefinition(request_method=EClient.reqMktDepthExchanges,
            update_methods=[EWrapper.mktDepthExchanges]),
        ApiDefinition(request_method=EClient.reqNewsArticle,
            update_methods=[EWrapper.newsArticle]),
        ApiDefinition(request_method=EClient.reqNewsProviders,
            update_methods=[EWrapper.newsProviders]),
        ApiDefinition(request_method=EClient.reqScannerParameters,
            update_methods=[EWrapper.scannerParameters]),
        ApiDefinition(request_method=EClient.reqSecDefOptParams,
            update_methods=[EWrapper.securityDefinitionOptionParameter],
            done_method=EWrapper.securityDefinitionOptionParameterEnd,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqSmartComponents,
            update_methods=[EWrapper.smartComponents],
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqSoftDollarTiers,
            update_methods=[EWrapper.softDollarTiers],
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.reqSoftDollarTiers,
            update_methods=[EWrapper.softDollarTiers],
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.requestFA,
            update_methods=[EWrapper.receiveFA]),
        ApiDefinition(request_method=EClient.setServerLogLevel),
        ApiDefinition(request_method=EClient.subscribeToGroupEvents,
            stream_methods=[EWrapper.displayGroupUpdated],
            cancel_method=EClient.unsubscribeFromGroupEvents,
            req_id_names=["reqId"]),
        ApiDefinition(request_method=EClient.updateDisplayGroup),
        ApiDefinition(request_method=None, stream_methods=[EWrapper.commissionReport]),
        ApiDefinition(request_method=None, stream_methods=[EWrapper.orderBound])
    ]
