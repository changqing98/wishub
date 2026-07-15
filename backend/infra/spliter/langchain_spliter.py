from langchain_text_splitters import MarkdownTextSplitter


def markdown_split(self, file):
    markdown_spliter = MarkdownTextSplitter(chunk_size=1000, chunk_overlap=0)
    markdown_spliter.split_text()
