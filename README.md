# Introduction

The goal of this package is to facilitate generation of wrappers around the TWS Python API to build services using OpenAPI, gRPC, asyncio, and other frameworks. This work is distinct from other projects in that it doesn't attempt to re-implement the TWS API. Instead, the API is left intact, and wrappers are generated on top of it.

Testing has been performed with TWS API 9.85.1.

# Examples

- [Example of using the asyncio API](./examples/test_requests.py)

# TWS API Setup

Interactive Brokers does not allow redistribution of the TWS API so it needs to be setup by accepting the license agreement via the following steps:

1. [Download the TWS API](https://interactivebrokers.github.io/#) 
2. After unzipping the downloaded file, follow the steps in the `source/pythonclient/README.md`. At the time of the writing the API can be setup by running the following commands in the `source/pythonclient` directory of the unzipped folder:
    1. python3 setup.py bdist_wheel
    2. python3 -m pip install --user --upgrade dist/ibapi-*-py3-none-any.whl

# TWS API Notes

## Threading

The TWS API uses the following threading model:

1. Messages from TWS are read from the socket via the `EReader` class in a dedicated thread and pushed into a queue. 
2. Messages to TWS can be sent from any thread via the `EClient` class, but is a blocking operation.
3. The main event loop for the `EClient` class, is responsible for decoding messages sent by TWS by taking them out of the queue used by `EReader`. The dequeue operation is blocking, so the `EClient` event loop is typically run in a dedicated thread.

## Patterns

The TWS API uses the following patterns:

1. Request a one time status. These have a single request method and a single response callback. 

    Example: `EClient.reqCurrentTime` and `EWrapper.currentTime` 

2. Request a subscription for account-wide state updates. These have the following methods:
    
    - A request method to start the subscription
    - A cancel method to stop the subscription
    - One or more update method for subscription updates
    - One ore more streaming methods for continues updates
    - For requests that return more than one update, a done method to indicate the end of a set of updates

    Example: `EClient.reqPositions`, `EClient.cancelPositions`, `EWrapper.position`, `EWrapper.positionEnd`

3. Request a subscription for state updates by request id. These have the same methods as those of 2. except they take an additional reqId parameter.

    Example: `EClient.reqPositionsMulti`, `EClient.cancelPositionsMulti`, `EWrapper.positionMulti`, `EWrapper.positionMultiEnd`

4. Fire and forget requests. These have a single request method. 

    Example: `EClient.setServerLogLevel`.

5. Other one-off patterns. These have the following methods:
    
    - A request method. 
    - An optional cancel method. 
    - One or more update methods. 
    - One or more streaming methods.
    - Sometimes there's a separate done method or a done flag may also be passed via the update method.

    Example `EClient.reqHistoricalTicks`, `EWrapper.historicalTicks`, `EWrapper.historicalTicksBidAsk`, `EWrapper.historicalTicksLast`

The high-level api definitions are captured in `ib_tws_server/api_definition.py`

# Code Generation

The code generation is implemented as part of the `codegen` module and can be run via `ib_tws_server/codegen/main.py`. 

The code generator assumes the TWS API is available as part of the normal module search path. Therefore, the TWS API version can be changed by modifying the module path either via overriding the `PYTHONPATH` environment variable, using Python virtual environments or any other mechanism. 

## Generated Classes

Classes are generated in the `ib_tws_server/gen` directory as part of the build. 

The following classes are generated:
- Response Classes:
    - A response class is generated for every request that has one or more callbacks.
    - The fields across all the update callbacks for a request are merged into a single class with the name `{RequestName}Response`.
    - The fields across all the streaming callbacks are merged into a single class with the name `{RequestName}Stream`.
- `IBAsyncioClient`: Exposes the relevant parts of the TWS API via asyncio semantics.
    - API Description:
        - Requests that have update callbacks asynchronously return a `{RequestName}Response`.
        - Requests that have streaming callbacks asynchronously return a `Subscription` instance that can be instance that can be used to cancel the subscription.
        - Requests that have both update and subscription callbacks will return a `({RequestName}Response, Subscription)` tuple
        - If a request uses a `done` flag or a done callback the request returns a `List{RequestName}Response` instead.
        - A streaming callback can be registered when calling the respective request method. The callbacks take a`{RequestName}Stream` argument.
        - Request ids are implicitly managed via the `Subscription` class. Requests that are not streaming cannot be cancelled.
    - Other improvements
        - To avoid blocking the asyncio running loop, an `IBWriter` class to write messages to TWS in a separate thread.

# Useful References

- [ib_insync library](https://github.com/erdewit/ib_insync/tree/master/ib_insync)
- Posts by Juri Sarbach to deploy TWS as a microservice:
    - [Post 1 ](https://medium.com/@juri.sarbach/building-my-own-cloud-based-robo-advisor-5588ec1b74d3)
    - [Post 2 Serverless](https://levelup.gitconnected.com/run-gateway-run-algorithmic-trading-the-serverless-way-71634dc1a37)
- [Guide to Interactive Brokers API Code](https://github.com/corbinbalzan/IBAPICode/blob/master/ExecOrders_Part2/ibProgram1.py)
