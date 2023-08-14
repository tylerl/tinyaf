import typing as t
T = t.TypeVar("T")

class Request: ...
class Response(t.Generic[T]):
    def set_header(self, key:str, val:str): ...
    def set_content(self, val: T): ...

class StringResponse(Response[str]):...
class FancyStringResponse(StringResponse):...
class BinaryResponse(Response[bytes]):...
class JsonResponse(Response[dict|list]):...

#Handler = t.Callable[[Request,Response[T]], T]
Wrapper = t.Callable[[T],T]

#ResponseT = t.TypeVar("ResponseT", bound=type(Response), contravariant=True)
ResponseT = t.TypeVar("ResponseT", bound=Response)
Handler = t.Callable[[Request, ResponseT], T]

def route(url: str) -> Wrapper[Handler[ResponseT, T]]: ...

TT = t.TypeVar("TT", contravariant=True, bound=type(Response))
VT = t.TypeVar("VT", contravariant=True, bound=type)
class HandlerP(t.Protocol[TT, VT]):
    @staticmethod
    def make():
        return type(TT)[VT]

hstr = HandlerP[type(Response[str]),type(str)].make()

@route("/")
def good(request: Request, response: FancyStringResponse):
    response.set_header("content-type", "text/html")
    return "hello world"

@route("/")
def bad(request: Request, response: FancyStringResponse):
    response.set_header("content-type", "text/html")
    return {'hello': 'world'}





# @route("/api")
# def api (request: Request, response: Response[dict]):
#     return {'status': 'OK'}


# T1 = TypeVar("T1")
# T2 = TypeVar("T2")

# FnType = Callable[[T1,T1],T2]

# def addints(a:int,b:int):
#     return a+b

# def xyz(myfn: FnType[int,str]):
#     s = myfn(1,2)
#     print(s)
