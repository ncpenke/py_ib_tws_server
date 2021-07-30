# Introduction

The goal of this package is to facilitate wrapping the Interactive Brokers TWS Python API to expose it as a service using GraphQL, and other frameworks. 

This work is distinct from other projects in that it doesn't attempt to re-implement the TWS API. Instead, the TWS API is used as is, and custom behavior is implemented through code generation and supporting classes.

Testing has been performed with TWS API 9.85.1.

# Examples

- [Example of using the asyncio API](./examples/test_requests.py)

# TWS API

The following section describes the Interactive Brokers TWS API setup and contains notes that describe the TWS API.

## TWS API Setup

Interactive Brokers does not allow redistribution of the TWS API so it needs to be setup by accepting the license agreement via the following steps:

1. [Download the TWS API](https://interactivebrokers.github.io/#) 
2. After unzipping the downloaded file, follow the steps in the `source/pythonclient/README.md`. At the time of the writing the API can be setup by running the following commands in the `source/pythonclient` directory of the unzipped folder:

    1. Install the wheel module via `pip3 install wheel`
    2. python3 setup.py bdist_wheel
    3. python3 -m pip install --user --upgrade dist/ibapi-*-py3-none-any.whl

The following are notes that characterize the TWS API to help with the design of this project.

## TWS API Threading Model

The TWS API uses the following threading model:

1. Messages from TWS are read from the socket via the `EReader` class in a dedicated thread and pushed into a queue. 
2. Messages to TWS can be sent from any thread via the `EClient` class, but is a blocking operation.
3. The main event loop for the `EClient` class, is responsible for decoding messages sent by TWS by taking them out of the queue used by `EReader`. The dequeue operation is blocking, so the `EClient` event loop is typically run in a dedicated thread.

## TWS API Patterns

The TWS API uses the following request/response patterns:

1. Queries that have a single item response. These have a single method to make a request, an optional method to cancel the request and a single callback for the response. 

    Example: `EClient.reqCurrentTime` and `EWrapper.currentTime` 

2. Queries that have a response consisting of a list of items. These have a single method to make a request, an optional method to cancel the request, and one or more callbacks for each item. Additionally, there's a method or flag in the callbacks to signal the end of the list.
    
    Example: `EClient.reqPositions`, `EClient.cancelPositions`, `EWrapper.position`, `EWrapper.positionEnd`

3. Subscriptions. These have a single method to start the subscription, a method to stop the subscription, and one or more callbacks for status updates.

    Example" `EClient.reqTickByTickData`, `EClient.tickByTickAllLast`, `EWrapper.tickByTickBidAsk` `EClient.cancelTickByTickData`

4. A variant of this pattern are requests that take a requestId parameter. This allows the same type of request to be issued with different parameters

    Example: `EClient.reqPositionsMulti`, `EClient.cancelPositionsMulti`, `EWrapper.positionMulti`, `EWrapper.positionMultiEnd`

5. Fire and forget requests. These have a single request method. 

    Example: `EClient.setServerLogLevel`.

6. A one-off pattern that wraps both a subscription and query in a single request call controlled by a flag.

    Example `EClient.reqHistoricalTicks`, `EWrapper.historicalTicks`, `EWrapper.historicalTicksBidAsk`, `EWrapper.historicalTicksLast`

# Code Generation

The code generation is implemented as part of the `codegen` module and can be run via [ib_tws_server/codegen/main.py](./ib_tws_server/codegen/main.py). 

The code generator assumes the TWS API is available as part of the python module search path. The TWS API version that the generator uses can be changed by modifying the module path via overriding the `PYTHONPATH` environment variable, using Python virtual environments, etc.

The code generator uses definitions captured in [ib_tws_server/api_definition.py](./ib_tws_server/api_definition.py). These definitions describe the TWS API in terms of patterns described in the [TWS API Patterns](#tws-api-patterns) section.

## Generated Classes

Classes are generated in the `ib_tws_server/gen` directory as part of the build. 

The following classes are generated:
- Callback Classes:
    - A top-level class is generated for every request that has one or more callbacks.
    - For callbacks for queries the response class has the name `{RequestName}Response`
    - For callbacks for subscriptions, the generated class has the name `{RequestName}Update`
    - All top-level classes also have an error code, and an error string to relay errors sent by TWS.
    - The top-level classes have member fields for each of the callbacks.
    - Additional classes are generated that encapsulate the parameters for each of the callbacks
- `IBAsyncioClient`: Subclasses `ibapi.wrapper.EWrapper` and `ibapi.client.EClient` to implement the callbacks expected by the TWS API and wrap around the TWS API with asyncio semantics.
    - All request methods are asynchronous and declared using `async`
    - Query methods that have a single item response return a `{RequestName}Response`. 
    - Query methods that have a response consisting of a list of items return a `List{RequestName}Response`.
    - Subscriptions return a `Subscription` instance that can be used to cancel the subscription, and additional take a callback that's queued on the running asyncio loop of the caller.
    - Request ids of the original TWS API are implicitly managed. 
    - Currently only subscriptions can be cancelled. Even though TWS API allows cancelling queries with multiple responses this is not exposed as part of the API. 
- Other improvements
    - To avoid blocking the asyncio running loop, an `IBWriter` class to send messages to TWS in a separate thread.

# Useful References

- [ib_insync library](https://github.com/erdewit/ib_insync/tree/master/ib_insync)
- Posts by Juri Sarbach to deploy TWS as a microservice:
    - [Post 1 ](https://medium.com/@juri.sarbach/building-my-own-cloud-based-robo-advisor-5588ec1b74d3)
    - [Post 2 Serverless](https://levelup.gitconnected.com/run-gateway-run-algorithmic-trading-the-serverless-way-71634dc1a37)
- [Guide to Interactive Brokers API Code](https://github.com/corbinbalzan/IBAPICode/blob/master/ExecOrders_Part2/ibProgram1.py)
