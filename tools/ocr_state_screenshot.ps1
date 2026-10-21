# Offline research helper: OCR a supplied image using an already-installed Windows
# recognizer. No game/app access, screenshots, downloads, model installation or network.
# $InputImage must be set by the caller to a local/UNC image file path.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
    $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
function Await-Result($operation, $resultType) {
    $task = $asTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
    $task.Wait() | Out-Null
    return $task.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
if (!$engine) { throw 'No installed OCR recognizer. No language pack will be downloaded.' }
# WinRT file access can reject WSL UNC paths. Copy only the supplied image into a
# unique temporary file; always dispose handles and delete it afterwards.
$temp = Join-Path ([System.IO.Path]::GetTempPath()) ('aoe2-coach-ocr-' + [Guid]::NewGuid().ToString() + '.png')
$stream = $null
$bitmap = $null
try {
    [System.IO.File]::Copy($InputImage, $temp, $false)
    $file = Await-Result ([Windows.Storage.StorageFile]::GetFileFromPathAsync($temp)) ([Windows.Storage.StorageFile])
    $stream = Await-Result ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await-Result ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await-Result ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $result = Await-Result ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    [PSCustomObject]@{
        schema_version = 1
        qualification = 'research_only_ocr_not_verified_game_state'
        provider = 'Windows.Media.Ocr.OcrEngine'
        language = $engine.RecognizerLanguage.LanguageTag
        width = $decoder.PixelWidth
        height = $decoder.PixelHeight
        text = $result.Text
        words = @($result.Lines | ForEach-Object { $_.Words } | ForEach-Object {
            [PSCustomObject]@{text=$_.Text; x=$_.BoundingRect.X; y=$_.BoundingRect.Y; width=$_.BoundingRect.Width; height=$_.BoundingRect.Height}
        })
    } | ConvertTo-Json -Depth 5
} finally {
    if ($bitmap) { $bitmap.Dispose() }
    if ($stream) { $stream.Dispose() }
    if ([System.IO.File]::Exists($temp)) { [System.IO.File]::Delete($temp) }
}
