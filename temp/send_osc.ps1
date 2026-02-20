$client = New-Object System.Net.Sockets.TcpClient
$client.Connect('127.0.0.1', 65432)
$stream = $client.GetStream()
$writer = New-Object System.IO.StreamWriter($stream)
$reader = New-Object System.IO.StreamReader($stream)

# Load EQ Eight on snare track (index 1)
$loadEQ = '{"jsonrpc":"2.0","id":"1","method":"send_message","params":{"address":"/live/track/load/device","args":[1,"Audio Effects/EQ Eight/EQ Eight.adv"]}}'

$writer.WriteLine($loadEQ)
$writer.Flush()
Start-Sleep -Milliseconds 2000

if($stream.DataAvailable){
    $response = $reader.ReadLine()
    Write-Host "Response:" $response
} else {
    Write-Host "No response received"
}

$client.Close()
