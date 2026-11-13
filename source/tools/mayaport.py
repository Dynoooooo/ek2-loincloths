"""Send a Python file to Maya's commandPort (localhost:7001) and print what comes back (the fallback when the maya
MCP is broken). The code runs through exec() inside Maya; reading stops at an end marker printed after it.
    python3 -I source/tools/mayaport.py code.py [timeout_s]
Keep the file under the port's 16 KB buffer (import modules from source/maya instead of inlining them)."""
import socket
import sys

END = "__MAYAPORT_END__"
code = open(sys.argv[1]).read()
timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 600
wrapped = "exec(compile(%r, '<port>', 'exec'), globals()); print(%r)" % (code, END)
s = socket.create_connection(("localhost", 7001), timeout=timeout)
s.sendall(wrapped.encode("utf-8"))
buf = b""
s.settimeout(timeout)
try:
    while END.encode() not in buf:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
    s.settimeout(1.0)
    while True:
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
except socket.timeout:
    pass
s.close()
out = buf.replace(b"\x00", b"\n").decode("utf-8", "replace")
print(out.replace(END, "")[-6000:])
