# Run as Administrator once: allow LAN devices to reach WhisPrompt.
# Without these rules the iPhone gets ERR_CONNECTION_TIMED_OUT.
New-NetFirewallRule -DisplayName "WhisPrompt HTTPS" -Direction Inbound `
    -Protocol TCP -LocalPort 8443 -Action Allow -Profile Private,Domain
New-NetFirewallRule -DisplayName "WhisPrompt HTTP helper" -Direction Inbound `
    -Protocol TCP -LocalPort 8000 -Action Allow -Profile Private,Domain
Write-Host "Done. If your Wi-Fi is categorized as 'Public', change it to 'Private' in Windows network settings."
