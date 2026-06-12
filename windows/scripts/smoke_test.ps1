# End-to-end smoke test without an iPhone:
# 1. Synthesizes a Chinese (fallback: English) speech WAV via Windows TTS
# 2. POSTs it to the running WhisPrompt server
# Usage: run windows\run.bat --headless first, then this script.
param(
    [string]$ServerUrl = "https://localhost:8443"
)

$wav = Join-Path $env:TEMP "whisprompt_test.wav"
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

$zh = $synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like "zh*" } | Select-Object -First 1
if ($zh) {
    $synth.SelectVoice($zh.VoiceInfo.Name)
    $text = "幫我寫一個程式,功能是把資料夾裡的圖片全部轉成PNG格式,然後依照日期重新命名。"
} else {
    $text = "Write a program that converts all images in a folder to PNG format and renames them by date."
}
$synth.SetOutputToWaveFile($wav)
$synth.Speak($text)
$synth.Dispose()
Write-Host "TTS wrote: $wav"
Write-Host "Spoken text: $text"

# PowerShell 5.1 lacks -SkipCertificateCheck and multipart helpers; use curl.exe (ships with Win10+).
$response = curl.exe -k -s -X POST "$ServerUrl/api/audio" -F "file=@$wav" -F "mode=prompt"
Write-Host "`n--- Server response ---"
$response | ConvertFrom-Json | Format-List
