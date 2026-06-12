import SwiftUI

struct ContentView: View {
    @StateObject private var recorder = Recorder()
    @AppStorage("serverURL") private var serverURL = "https://192.168.1.100:8443"
    @AppStorage("mode") private var mode = "prompt"

    @State private var statusText = "未連線"
    @State private var connected = false
    @State private var modes: [String: String] = ["prompt": "優化為 prompt", "clean": "僅修正錯漏字", "raw": "原始轉錄"]
    @State private var busy = false
    @State private var result: TranscriptionResult?
    @State private var errorMessage: String?
    @State private var showSettings = false

    private var client: APIClient? {
        URL(string: serverURL).map(APIClient.init)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    modePicker
                    recordButton
                    statusLine
                    if let result { resultCards(result) }
                }
                .padding()
            }
            .navigationTitle("WhisPrompt")
            .toolbar {
                Button { showSettings = true } label: { Image(systemName: "gear") }
            }
            .sheet(isPresented: $showSettings) { settingsSheet }
            .task { await connect() }
        }
    }

    private var modePicker: some View {
        Picker("模式", selection: $mode) {
            ForEach(modes.sorted(by: { $0.key < $1.key }), id: \.key) { key, label in
                Text(label).tag(key)
            }
        }
        .pickerStyle(.segmented)
    }

    private var recordButton: some View {
        Button {
            Task { await toggleRecording() }
        } label: {
            ZStack {
                Circle()
                    .stroke(recorder.isRecording ? Color.red : Color.accentColor, lineWidth: 4)
                    .frame(width: 132, height: 132)
                if busy {
                    ProgressView().controlSize(.large)
                } else {
                    RoundedRectangle(cornerRadius: recorder.isRecording ? 8 : 22)
                        .fill(Color.red)
                        .frame(width: recorder.isRecording ? 38 : 44,
                               height: recorder.isRecording ? 38 : 44)
                        .animation(.easeInOut(duration: 0.2), value: recorder.isRecording)
                }
            }
        }
        .disabled(busy || !connected)
        .padding(.vertical, 12)
    }

    private var statusLine: some View {
        VStack(spacing: 6) {
            if recorder.isRecording {
                Text(timeString(recorder.elapsed)).font(.title3.monospacedDigit())
            }
            Text(errorMessage ?? statusText)
                .font(.footnote)
                .foregroundStyle(errorMessage != nil ? .red : .secondary)
        }
    }

    private func resultCards(_ r: TranscriptionResult) -> some View {
        VStack(spacing: 14) {
            card(title: "優化後 Prompt", text: r.prompt)
            card(title: "原始轉錄 · \(String(format: "%.1f", r.duration))s · \(r.language)",
                 text: r.transcript.isEmpty ? "(無語音內容)" : r.transcript)
        }
    }

    private func card(title: String, text: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(title).font(.caption).foregroundStyle(.secondary)
                Spacer()
                Button("複製") { UIPasteboard.general.string = text }
                    .font(.caption.bold())
                    .buttonStyle(.bordered)
            }
            Text(text).frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 14))
    }

    private var settingsSheet: some View {
        NavigationStack {
            Form {
                Section("伺服器") {
                    TextField("https://192.168.x.x:8443", text: $serverURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button("重新連線") {
                        showSettings = false
                        Task { await connect() }
                    }
                }
                Section {
                    Text("首次使用需在 iPhone 安裝並信任電腦產生的憑證:用 Safari 開啟 Windows 程式顯示的 http 設定頁。")
                        .font(.footnote).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("設定")
        }
    }

    // MARK: - actions

    private func connect() async {
        errorMessage = nil
        guard let client else {
            errorMessage = "伺服器網址格式錯誤"
            return
        }
        do {
            let s = try await client.status()
            statusText = "\(s.whisper_model) (\(s.whisper_device)) · \(s.ollama_model)"
            modes = s.modes
            connected = true
        } catch {
            connected = false
            errorMessage = "無法連線: \(error.localizedDescription)"
        }
    }

    private func toggleRecording() async {
        errorMessage = nil
        if recorder.isRecording {
            guard let url = recorder.stop(), let client else { return }
            busy = true
            statusText = "轉錄與優化中..."
            do {
                let r = try await client.upload(audio: url, mode: mode)
                result = r
                statusText = "完成 (\(String(format: "%.1f", r.elapsed))s)"
                UIPasteboard.general.string = r.prompt
            } catch {
                errorMessage = error.localizedDescription
            }
            busy = false
        } else {
            do {
                result = nil
                try await recorder.start()
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }

    private func timeString(_ t: TimeInterval) -> String {
        String(format: "%02d:%02d", Int(t) / 60, Int(t) % 60)
    }
}

#Preview {
    ContentView()
}
