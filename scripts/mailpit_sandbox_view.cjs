// Fixed-upstream loopback inspector; no database mounts or backend credentials.
const http = require('node:http');
const upstream = { hostname: 'mailpit-sandbox', port: 8025 };

function allowed(request) {
  try {
    const host = new URL('http://' + request.headers.host).hostname;
    const origin = request.headers.origin;
    if (origin && origin !== 'http://' + request.headers.host) return false;
    return ['localhost', '127.0.0.1', '[::1]'].includes(host)
      && request.url.startsWith('/') && !request.url.startsWith('//');
  } catch {
    return false;
  }
}

function options(request) {
  return { ...upstream, path: request.url, method: request.method,
    headers: { ...request.headers, host: 'mailpit-sandbox:8025' } };
}

const server = http.createServer((request, response) => {
  if (!allowed(request)) {
    response.writeHead(403).end('Local inbox access only');
    return;
  }
  const remote = http.request(options(request), incoming => {
    response.writeHead(incoming.statusCode, incoming.headers);
    incoming.pipe(response);
  });
  remote.setTimeout(10000, () => remote.destroy());
  remote.on('error', () => {
    if (!response.headersSent) response.writeHead(502);
    response.end('Mailpit sandbox is not available.');
  });
  request.on('aborted', () => remote.destroy());
  request.pipe(remote);
});

// Preserve Mailpit's inbox update stream without opening another host port.
server.on('upgrade', (request, socket, head) => {
  if (!allowed(request)) {
    socket.end('HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n');
    return;
  }
  const remote = http.request(options(request));
  remote.on('upgrade', (response, other, otherHead) => {
    socket.write('HTTP/1.1 101 Switching Protocols\r\n'
      + Object.entries(response.headers).map(([key, value]) => key + ': ' + value).join('\r\n')
      + '\r\n\r\n');
    if (head.length) other.write(head);
    if (otherHead.length) socket.write(otherHead);
    socket.on('error', () => other.destroy());
    other.on('error', () => socket.destroy());
    socket.pipe(other).pipe(socket);
  });
  remote.on('response', () => socket.destroy());
  remote.on('error', () => socket.destroy());
  socket.on('error', () => remote.destroy());
  remote.end();
});
server.listen(8025, '0.0.0.0');
