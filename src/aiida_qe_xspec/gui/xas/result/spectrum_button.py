import base64
from typing import Callable

import ipywidgets as ipw


class SpectrumDownloadButton(ipw.Button):
    """Download button with dynamic content.

    Javascript solution copied from AiiDALab-QE
    archive download function.
    (see: https://github.com/aiidalab/aiidalab-qe/blob/main/src/aiidalab_qe/app/result/components/summary/download_data.py)
    """

    def __init__(self, filename: str, contents: Callable[[], str], **kwargs):
        super().__init__(**kwargs)
        self.filename = filename
        self.contents = contents
        self.on_click(self.__on_click)

    def __on_click(self, _):
        from IPython.display import Javascript, display
        if self.contents is None:
            return

        contents: bytes = self.contents().encode('utf-8')
        b64 = base64.b64encode(contents)
        payload = b64.decode()
        javas = Javascript(
            f"""
            var link = document.createElement('a');
            link.href = 'data:application;base64,{payload}'
            link.download = '{self.filename}'
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            """
        )
        display(javas)
