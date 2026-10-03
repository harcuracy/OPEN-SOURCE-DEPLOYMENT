# Comprehensive Voice AI Test Script (LLM + Kokoro TTS + Faster-Whisper STT)
$baseUrl = "http://127.0.0.1:8000"
$apiKey  = "tingo-master-key-1234567890abcdef"

$headers = @{
    "Authorization" = "Bearer $apiKey"
}

Write-Host "1. Testing Gateway Aggregated Health (checks Gateway, LLM, TTS, STT)..." -ForegroundColor Cyan
Invoke-RestMethod -Uri "$baseUrl/health" -Method Get | ConvertTo-Json

Write-Host "`n2. Listing Available Models..." -ForegroundColor Cyan
$modelsRes = Invoke-RestMethod -Uri "$baseUrl/v1/models" -Method Get -Headers $headers
$modelsRes | ConvertTo-Json

Write-Host "`n3. Testing LLM Chat Completion (Mistral 7B)..." -ForegroundColor Cyan
$jsonHeaders = @{
    "Content-Type"  = "application/json"
    "Authorization" = "Bearer $apiKey"
}

$chatBody = @{
    model = "mistral-7b"
    messages = @(
        @{ role = "user"; content = "Say 'Voice AI loop active' in 4 words." }
    )
    max_tokens = 50
} | ConvertTo-Json

$chatRes = Invoke-RestMethod -Uri "$baseUrl/v1/chat/completions" -Method Post -Headers $jsonHeaders -Body $chatBody
$llmAnswer = $chatRes.choices[0].message.content.Trim()
Write-Host "LLM Output: " -NoNewline
Write-Host $llmAnswer -ForegroundColor Green

Write-Host "`n4. Testing Kokoro TTS: Synthesizing voice to kokoro_test.wav..." -ForegroundColor Cyan
$speechBody = @{
    model = "kokoro"
    input = "Hello! This voice was synthesized with Kokoro and will now be transcribed by Whisper."
    voice = "af_heart"
    speed = 1.0
} | ConvertTo-Json

$outFile = "kokoro_test.wav"
if (Test-Path $outFile) { Remove-Item $outFile -Force }
try {
    Invoke-RestMethod -Uri "$baseUrl/v1/audio/speech" -Method Post -Headers $jsonHeaders -Body $speechBody -OutFile $outFile
} catch {
    Write-Host "TTS synthesis failed: $_" -ForegroundColor Red
}

if (Test-Path $outFile) {
    $size = (Get-Item $outFile).Length
    Write-Host "Audio synthesized successfully: $outFile ($size bytes)" -ForegroundColor Green

    Write-Host "`n5. Testing Faster-Whisper STT: Transcribing the audio back to text..." -ForegroundColor Cyan
    
    # Send multipart/form-data with the audio file to /v1/audio/transcriptions
    $boundary = [System.Guid]::NewGuid().ToString()
    $fileBytes = [System.IO.File]::ReadAllBytes((Resolve-Path $outFile))
    
    $LF = "`r`n"
    $bodyLines = @(
        "--$boundary",
        "Content-Disposition: form-data; name=`"file`"; filename=`"$outFile`"",
        "Content-Type: audio/wav",
        "",
        [System.Text.Encoding]::GetEncoding("iso-8859-1").GetString($fileBytes),
        "--$boundary",
        "Content-Disposition: form-data; name=`"model`"",
        "",
        "whisper-1",
        "--$boundary--",
        ""
    )
    $formBody = [System.Text.Encoding]::GetEncoding("iso-8859-1").GetBytes(($bodyLines -join $LF))

    $sttHeaders = @{
        "Authorization" = "Bearer $apiKey"
        "Content-Type"  = "multipart/form-data; boundary=$boundary"
    }

    $sttRes = Invoke-RestMethod -Uri "$baseUrl/v1/audio/transcriptions" -Method Post -Headers $sttHeaders -Body $formBody
    Write-Host "Whisper Transcription: " -NoNewline
    Write-Host $sttRes.text -ForegroundColor Green
    Write-Host "`nFull Voice AI Loop Completed Successfully!" -ForegroundColor Cyan
} else {
    Write-Host "Audio generation failed; skipping STT test." -ForegroundColor Red
}
