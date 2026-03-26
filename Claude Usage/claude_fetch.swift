import Foundation

// argv[1] = sessionKey, argv[2] = orgId
guard CommandLine.arguments.count >= 3 else {
    print("{\"error\": \"Usage: claude_fetch_helper <sessionKey> <orgId>\"}")
    exit(1)
}

let session = CommandLine.arguments[1]
let orgId   = CommandLine.arguments[2]
let semaphore = DispatchSemaphore(value: 0)
var output = ""

var req = URLRequest(url: URL(string: "https://claude.ai/api/organizations/\(orgId)/usage")!)
req.setValue("sessionKey=\(session)", forHTTPHeaderField: "Cookie")
req.setValue("web",              forHTTPHeaderField: "anthropic-client-type")
req.setValue("application/json", forHTTPHeaderField: "Accept")
req.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
             forHTTPHeaderField: "User-Agent")
req.timeoutInterval = 10

URLSession.shared.dataTask(with: req) { data, resp, err in
    if let data = data, let s = String(data: data, encoding: .utf8) {
        output = s
    } else {
        output = "{\"error\": \"\(err?.localizedDescription ?? "unknown")\"}"
    }
    semaphore.signal()
}.resume()
semaphore.wait()
print(output)
