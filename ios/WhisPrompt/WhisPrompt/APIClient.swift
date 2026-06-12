import Foundation

struct TranscriptionResult: Decodable {
    let transcript: String
    let prompt: String
    let duration: Double
    let language: String
    let elapsed: Double
}

struct ServerStatus: Decodable {
    let whisper_model: String
    let whisper_device: String
    let ollama_model: String
    let mode: String
    let modes: [String: String]
}

struct APIClient {
    let baseURL: URL

    func status() async throws -> ServerStatus {
        let (data, _) = try await URLSession.shared.data(from: baseURL.appendingPathComponent("api/status"))
        return try JSONDecoder().decode(ServerStatus.self, from: data)
    }

    func upload(audio: URL, mode: String) async throws -> TranscriptionResult {
        var request = URLRequest(url: baseURL.appendingPathComponent("api/audio"))
        request.httpMethod = "POST"
        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var body = Data()
        func field(_ s: String) { body.append(s.data(using: .utf8)!) }

        field("--\(boundary)\r\n")
        field("Content-Disposition: form-data; name=\"mode\"\r\n\r\n\(mode)\r\n")
        field("--\(boundary)\r\n")
        field("Content-Disposition: form-data; name=\"file\"; filename=\"recording.m4a\"\r\n")
        field("Content-Type: audio/mp4\r\n\r\n")
        body.append(try Data(contentsOf: audio))
        field("\r\n--\(boundary)--\r\n")

        let (data, response) = try await URLSession.shared.upload(for: request, from: body)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            let message = String(data: data, encoding: .utf8) ?? "unknown"
            throw NSError(domain: "APIClient", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "伺服器錯誤: \(message)"])
        }
        return try JSONDecoder().decode(TranscriptionResult.self, from: data)
    }
}
