"""Shared test helpers."""


def call_tool(tool_obj, *args, **kwargs):
    """Call a FastMCP @mcp.tool() decorated function.

    FastMCP wraps functions in FunctionTool objects.  The raw callable
    lives at ``tool_obj.fn``.  This helper transparently unwraps it so
    tests can call ``call_tool(module.some_tool, ...)`` regardless of
    whether the object is a plain function or a FunctionTool.
    """
    fn = getattr(tool_obj, "fn", tool_obj)
    return fn(*args, **kwargs)
