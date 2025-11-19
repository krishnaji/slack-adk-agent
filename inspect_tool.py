import inspect
from google.adk.tools import VertexAiSearchTool

print(inspect.signature(VertexAiSearchTool.__init__))
print(VertexAiSearchTool.__init__.__doc__)
