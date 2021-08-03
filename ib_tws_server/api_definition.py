from dataclasses import dataclass
from typing_extensions import TypeAlias
from ib_tws_server.ib_imports import *
import inspect
import logging
from typing import Callable, Dict, FrozenSet, List, MutableSet, Set, Type

logger = logging.getLogger(__name__)

class ApiDefinition:
    request_method: Callable = None
    cancel_method: Callable = None
    callback_methods: List[Callable] = None
    done_method: Callable = None
    uses_req_id: bool = False
    has_done_flag: bool = False
    is_subscription: bool = False
    subscription_flag_name: str = None
    subscription_flag_value: bool = True

    def __init__(self, request_method: Callable, 
        cancel_method: Callable = None, 
        callback_methods: List[Callable] = None, 
        done_method: Callable = None, 
        uses_req_id: bool = False, 
        has_done_flag: bool = False,
        is_subscription: bool = False,
        subscription_flag_name: str = None,
        subscription_flag_value: bool = True):
        self.request_method = request_method
        self.cancel_method = cancel_method
        self.callback_methods = callback_methods
        self.done_method = done_method
        self.uses_req_id = uses_req_id
        self.has_done_flag = has_done_flag
        self.is_subscription = is_subscription
        self.subscription_flag_name = subscription_flag_name
        self.subscription_flag_value = subscription_flag_value

        if self.is_subscription or self.subscription_flag_name is not None:
            if not self.callback_methods or len(self.callback_methods) == 0:
                raise RuntimeError(f"Subscriptions should always have one or more callbacks {request_method.__name__}")

        if self.subscription_flag_name is not None:
            self.is_subscription = False

    @staticmethod
    def verify():
        ignore_methods = IGNORE_METHODS.copy()

        def log_unprocessed_methods():
            predicate = lambda x: inspect.isfunction(x) and not inspect.isbuiltin(x) and not inspect.ismethoddescriptor(x) and not x.__name__.startswith("__")
            for name,val in inspect.getmembers(EClient, predicate): 
                if not val in ignore_methods:
                    logger.error(f"Unhandled request: {name}")
            for name,type in inspect.getmembers(EWrapper, predicate):
                if not val in ignore_methods:
                    logger.error(f"Unhandled response: {name}")

        def flag_request_definition(definition: ApiDefinition):
            if (definition.request_method is not None):
                ignore_methods.add(definition.request_method)
            if (definition.cancel_method is not None):
                ignore_methods.add(definition.cancel_method)
            if (definition.callback_methods is not None):
                for m in definition.callback_methods: 
                    ignore_methods.add(m)
            if (definition.done_method is not None):
                ignore_methods.add(definition.done_method)


        for d in REQUEST_DEFINITIONS: flag_request_definition(d)
        log_unprocessed_methods()

class TypeDefinition:
    container_type: type
    item_type: str

    def __init__(self, container_type: type, item_type: str):
        self.container_type = container_type
        self.item_type = item_type

IGNORE_METHODS: FrozenSet[Callable] = set({
    EClient.connect,
    EWrapper.connectAck,
    EWrapper.connectionClosed,
    EClient.disconnect,
    EWrapper.error,
    EClient.isConnected,
    EClient.keyboardInterrupt,
    EClient.keyboardInterruptHard,
    EWrapper.logAnswer,
    EClient.logRequest,
    EClient.msgLoopRec,
    EClient.msgLoopTmo,
    EClient.reset,
    EClient.run,
    EClient.sendMsg,
    EClient.serverVersion,
    EClient.setConnState,
    EClient.setConnectionOptions,
    EClient.startApi,
    EClient.twsConnectionTime,
    EWrapper.verifyAndAuthCompleted,
    EClient.verifyAndAuthMessage,
    EWrapper.verifyAndAuthMessageAPI,
    EClient.verifyAndAuthRequest,
    EWrapper.verifyCompleted,
    EClient.verifyMessage,
    EWrapper.verifyMessageAPI,
    EClient.verifyRequest,
    EWrapper.winError
})

# Mappings of requests with their callbacks.
REQUEST_DEFINITIONS: List[ApiDefinition] = [
    ApiDefinition(request_method=EClient.queryDisplayGroups, 
        callback_methods=[EWrapper.displayGroupList],
        uses_req_id=True),
    ApiDefinition(request_method=EClient.exerciseOptions, uses_req_id=True),
    ApiDefinition(request_method=EClient.calculateImpliedVolatility, 
        callback_methods=[EWrapper.tickOptionComputation],
        cancel_method=EClient.cancelCalculateImpliedVolatility,
        is_subscription = True,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.calculateOptionPrice, 
        callback_methods=[EWrapper.tickOptionComputation],
        cancel_method=EClient.cancelCalculateOptionPrice,
        is_subscription = True,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqAccountSummary, 
        callback_methods=[EWrapper.accountSummary],
        cancel_method=EClient.cancelAccountSummary,
        done_method=EWrapper.accountSummaryEnd,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqAccountUpdatesMulti, 
        callback_methods=[EWrapper.accountUpdateMulti],
        cancel_method=EClient.cancelAccountUpdatesMulti,
        done_method=EWrapper.accountUpdateMultiEnd,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqFundamentalData, 
        callback_methods=[EWrapper.fundamentalData],
        cancel_method=EClient.cancelFundamentalData,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqHeadTimeStamp, 
        callback_methods=[EWrapper.headTimestamp],
        cancel_method=EClient.cancelHeadTimeStamp,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqHistogramData, 
        callback_methods=[EWrapper.histogramData],
        cancel_method=EClient.cancelHistogramData,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqHistoricalData, 
        callback_methods=[EWrapper.historicalData, EWrapper.historicalDataUpdate],
        cancel_method=EClient.cancelHistoricalData,
        done_method=EWrapper.historicalDataEnd,
        subscription_flag_name = 'keepUpToDate',
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqMktData, 
        callback_methods=[EWrapper.tickPrice, EWrapper.tickSize, 
            EWrapper.tickEFP,
            EWrapper.tickNews, EWrapper.rerouteMktDataReq, 
            EWrapper.rerouteMktDepthReq, EWrapper.tickReqParams, 
            EWrapper.deltaNeutralValidation],
        cancel_method=EClient.cancelMktData,
        done_method=EWrapper.tickSnapshotEnd,
        subscription_flag_name = 'snapshot',
        subscription_flag_value = False,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqMktDepth, 
        callback_methods=[EWrapper.updateMktDepth, EWrapper.updateMktDepthL2],
        cancel_method=EClient.cancelMktDepth,
        is_subscription = True,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqNewsBulletins,
        callback_methods=[EWrapper.updateNewsBulletin],
        cancel_method=EClient.cancelNewsBulletins,
        is_subscription = True),
    ApiDefinition(request_method=EClient.placeOrder,
        callback_methods=[EWrapper.orderStatus],
        is_subscription = True,
        cancel_method=EClient.cancelOrder),
    ApiDefinition(request_method=EClient.reqPnL,
        callback_methods=[EWrapper.pnl],
        cancel_method=EClient.cancelPnL,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqPnLSingle,
        callback_methods=[EWrapper.pnlSingle],
        cancel_method=EClient.cancelPnLSingle,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqPositions,
        callback_methods=[EWrapper.position],
        done_method=EWrapper.positionEnd,
        cancel_method=EClient.cancelPositions),
    ApiDefinition(request_method=EClient.reqPositionsMulti,
        callback_methods=[EWrapper.positionMulti],
        done_method=EWrapper.positionMultiEnd,
        cancel_method=EClient.cancelPositionsMulti,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqRealTimeBars,
        callback_methods=[EWrapper.realtimeBar],
        cancel_method=EClient.cancelRealTimeBars,
        is_subscription = True,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqScannerSubscription,
        callback_methods=[EWrapper.scannerData],
        done_method=EWrapper.scannerDataEnd,
        cancel_method=EClient.cancelScannerSubscription,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqTickByTickData,
        callback_methods=[EWrapper.tickByTickAllLast, EWrapper.tickByTickBidAsk, EWrapper.tickByTickMidPoint],
        cancel_method=EClient.cancelTickByTickData,
        is_subscription = True,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.replaceFA,
        done_method=EWrapper.replaceFAEnd,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqAccountUpdates,
        callback_methods=[EWrapper.updateAccountValue, EWrapper.updateAccountTime, EWrapper.updatePortfolio],
        done_method=EWrapper.accountDownloadEnd),
    ApiDefinition(request_method=EClient.reqOpenOrders),
    ApiDefinition(request_method=EClient.reqAllOpenOrders),
    ApiDefinition(request_method=EClient.reqAutoOpenOrders),
    ApiDefinition(request_method=EClient.reqContractDetails,
        callback_methods=[EWrapper.contractDetails,EWrapper.bondContractDetails],
        done_method=EWrapper.contractDetailsEnd,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqCurrentTime,
        callback_methods=[EWrapper.currentTime]),
    ApiDefinition(request_method=EClient.reqCompletedOrders,
        callback_methods=[EWrapper.completedOrder],
        done_method=EWrapper.completedOrdersEnd),
    ApiDefinition(request_method=EClient.reqExecutions,
        callback_methods=[EWrapper.execDetails],
        done_method=EWrapper.execDetailsEnd,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqFamilyCodes,
        callback_methods=[EWrapper.familyCodes]),
    ApiDefinition(request_method=EClient.reqGlobalCancel),
    ApiDefinition(request_method=EClient.reqHistoricalNews,
        callback_methods=[EWrapper.historicalNews],
        done_method=EWrapper.historicalNewsEnd,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqHistoricalTicks,
        callback_methods=[EWrapper.historicalTicks, EWrapper.historicalTicksBidAsk, EWrapper.historicalTicksLast],
        uses_req_id=True,
        has_done_flag=True),
    ApiDefinition(request_method=EClient.reqIds,
        callback_methods=[EWrapper.nextValidId]),
    ApiDefinition(request_method=EClient.reqManagedAccts,
        callback_methods=[EWrapper.managedAccounts]),
    ApiDefinition(request_method=EClient.reqMarketDataType),
    ApiDefinition(request_method=EClient.reqMarketRule,
        callback_methods=[EWrapper.marketRule]),
    ApiDefinition(request_method=EClient.reqMatchingSymbols,
        callback_methods=[EWrapper.symbolSamples]),
    ApiDefinition(request_method=EClient.reqMktDepthExchanges,
        callback_methods=[EWrapper.mktDepthExchanges]),
    ApiDefinition(request_method=EClient.reqNewsArticle,
        callback_methods=[EWrapper.newsArticle]),
    ApiDefinition(request_method=EClient.reqNewsProviders,
        callback_methods=[EWrapper.newsProviders]),
    ApiDefinition(request_method=EClient.reqScannerParameters,
        callback_methods=[EWrapper.scannerParameters]),
    ApiDefinition(request_method=EClient.reqSecDefOptParams,
        callback_methods=[EWrapper.securityDefinitionOptionParameter],
        done_method=EWrapper.securityDefinitionOptionParameterEnd,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqSmartComponents,
        callback_methods=[EWrapper.smartComponents],
        uses_req_id=True),
    ApiDefinition(request_method=EClient.reqSoftDollarTiers,
        callback_methods=[EWrapper.softDollarTiers],
        uses_req_id=True),
    ApiDefinition(request_method=EClient.requestFA,
        callback_methods=[EWrapper.receiveFA]),
    ApiDefinition(request_method=EClient.setServerLogLevel),
    ApiDefinition(request_method=EClient.subscribeToGroupEvents,
        callback_methods=[EWrapper.displayGroupUpdated],
        cancel_method=EClient.unsubscribeFromGroupEvents,
        is_subscription = True,
        uses_req_id=True),
    ApiDefinition(request_method=EClient.updateDisplayGroup),
    ApiDefinition(request_method=None, callback_methods=[EWrapper.commissionReport]),
    ApiDefinition(request_method=None, callback_methods=[EWrapper.marketDataType]),
    ApiDefinition(request_method=None, callback_methods=[EWrapper.orderBound, EWrapper.orderStatus,EWrapper.openOrder,EWrapper.openOrderEnd])
]

class OverriddenTypeAliases:
    """Missing or incomplete type aliases"""
    SetOfString = Set[str]
    SetOfFloat = Set[float]
    ListOfOrder = List[Order]
    ListOfFamilyCode = List[FamilyCode]
    ListOfContractDescription = List[ContractDescription]
    ListOfDepthExchanges = List[DepthMktDataDescription]
    ListOfNewsProviders = List[NewsProvider]
    HistogramDataList = List[HistogramData]
    ListOfPriceIncrements = List[PriceIncrement]
    ListOfHistoricalTick = List[HistoricalTick]
    ListOfHistoricalTickBidAsk = List[HistoricalTickBidAsk]
    ListOfHistoricalTickLast = List[HistoricalTickLast]
    TagValueList = List[TagValue]
    SoftDollarTierList = List[SoftDollarTier]
    SmartComponentMap = Dict[str, SmartComponent]
    OrderId = int

class EnumAliases:
    """The types that are aliased by enums. This is used to generate conversion methods
    to/from the enum type. These are strings to get the original class from globals"""
    TickType = 'TickTypeEnum'
    FaDataType = 'FaDataTypeEnum'
    MarketDataType = 'MarketDataTypeEnum'

class OverriddenMemberTypeHints:
    """Missing or incorrect hints for members"""
    class Order:
        algoParams = OverriddenTypeAliases.TagValueList
        conditions = List[OrderCondition]
        orderComboLegs = List[OrderComboLeg]
        orderMiscOptions = List[TagValue]
        smartComboRoutingParams = OverriddenTypeAliases.TagValueList
        usePriceMgmtAlgo = bool
    class Contract: 
        comboLegs = List[ComboLeg]
        deltaNeutralContract = DeltaNeutralContract
    class ContractDetails:
        secIdList = List[str]
    class ContractDescription:
        derivativeSecTypes = List[str]
    class SoftDollarTiers:
        tiers = List[SoftDollarTier]

class OverriddenMethodSignatures:
    """Missing or incorrect method signatures"""
    softDollarTiers = 'def softDollarTiers(self, reqId: int, tiers: SoftDollarTierList)'
