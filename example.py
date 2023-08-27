import tinyaf as tinyaf

app = tinyaf.App()

import typing as t

class CrazyResponse(tinyaf.StringResponse):
    def finalize(self, request: tinyaf.Request) -> None | bytes:
        self._str_list.insert(0, "Crazy:</br>")
        return super().finalize(request)
    def set_content(self, content:str):
        return super().set_content(content)

resp: tinyaf.Response = CrazyResponse()


@app.route("/")
def home(request: tinyaf.Request, response: tinyaf.JsonResponse):
    #response.set_content("Hello")
    #return response
    #return object()
    return ["Hello World"]

def main():
    """Program entry point."""
    print(app.routes)

    app.serve_forever()


if __name__ == "__main__":
    main()
