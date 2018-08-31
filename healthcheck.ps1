if !(Get-NetTCPConnection -RemotePort [28015] -State Established) {
    exit 1
}
if !(Get-NetTCPConnection -LocalPort [${PORT}] -Or Get-NetUDPEndpoint -LocalPort [${PORT}]) {
    exit 1
}
exit 0