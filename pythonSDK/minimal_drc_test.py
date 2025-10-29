#!/usr/bin/env python3
"""
Minimal DRC Mode Test

Test drc_mode_enter response handling with detailed debug output.
"""

import time
from djisdk import MQTTClient, ServiceCaller
from rich.console import Console

console = Console()

# Configuration
GATEWAY_SN = '9N9CN2J0012CXY'
MQTT_CONFIG = {
    'host': '81.70.222.38',
    'port': 1883,
    'username': 'dji',
    'password': 'lab605605'
}

def main():
    console.print("[bold cyan]=======================================[/bold cyan]")
    console.print("[bold cyan]   Minimal DRC Mode Test[/bold cyan]")
    console.print("[bold cyan]=======================================[/bold cyan]\n")

    # Step 1: Connect MQTT
    console.print("[bold yellow][Step 1] Connect MQTT[/bold yellow]")
    console.print(f"[dim]Target: {MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}[/dim]")

    try:
        mqtt_client = MQTTClient(GATEWAY_SN, MQTT_CONFIG)
        mqtt_client.connect()
        console.print("[green]OK: MQTT connected[/green]\n")
    except Exception as e:
        console.print(f"[red]ERROR: MQTT connection failed: {e}[/red]")
        return 1

    # Step 2: Create ServiceCaller
    console.print("[bold yellow][Step 2] Create ServiceCaller[/bold yellow]")
    caller = ServiceCaller(mqtt_client)
    console.print("[green]OK: ServiceCaller created[/green]\n")

    # Step 3: Request control auth
    console.print("[bold yellow][Step 3] Request Control Auth[/bold yellow]")

    try:
        console.print("[dim]Calling cloud_control_auth_request...[/dim]")
        result = caller.call("cloud_control_auth_request", {
            "user_id": "test_user",
            "user_callsign": "Test Callsign",
            "control_keys": ["flight"]
        })
        console.print(f"[blue]Response data: {result}[/blue]")
        console.print("[green]OK: Control auth granted[/green]\n")
    except Exception as e:
        console.print(f"[red]ERROR: Control auth failed: {e}[/red]")
        mqtt_client.disconnect()
        return 1

    # Step 4: Wait for user confirmation
    console.print("[bold yellow][Step 4] Wait for User Confirmation[/bold yellow]")
    input("Please allow control in DJI Pilot APP, then press Enter...\n")

    # Step 5: Enter DRC mode (KEY STEP)
    console.print("[bold yellow][Step 5] Enter DRC Mode (KEY STEP)[/bold yellow]")

    mqtt_broker_config = {
        'address': f"{MQTT_CONFIG['host']}:{MQTT_CONFIG['port']}",
        'client_id': f"drc-{GATEWAY_SN}",
        'username': MQTT_CONFIG['username'],
        'password': MQTT_CONFIG['password'],
        'expire_time': int(time.time()) + 3600,
        'enable_tls': False
    }

    console.print("[dim]MQTT Broker Config:[/dim]")
    console.print(f"[dim]  - address: {mqtt_broker_config['address']}[/dim]")
    console.print(f"[dim]  - client_id: {mqtt_broker_config['client_id']}[/dim]")
    console.print(f"[dim]  - username: {mqtt_broker_config['username']}[/dim]")
    console.print(f"[dim]  - expire_time: {mqtt_broker_config['expire_time']}[/dim]")
    console.print(f"[dim]  - enable_tls: {mqtt_broker_config['enable_tls']}[/dim]\n")

    try:
        console.print("[cyan]-> Sending drc_mode_enter request...[/cyan]")

        # Call directly to see raw response
        result = caller.call("drc_mode_enter", {
            "mqtt_broker": mqtt_broker_config,
            "osd_frequency": 100,
            "hsi_frequency": 10
        })

        console.print("[cyan]<- Received response[/cyan]")
        console.print(f"[blue]Raw response: {result}[/blue]")
        console.print(f"[blue]Response type: {type(result)}[/blue]")

        # Parse response
        if isinstance(result, dict):
            console.print("\n[yellow]Response breakdown:[/yellow]")
            for key, value in result.items():
                console.print(f"[yellow]  - {key}: {value}[/yellow]")

            # Check success/failure
            if result.get('result') == 0:
                console.print("\n[green]OK: DRC mode entered successfully (result=0)[/green]")
            else:
                console.print(f"\n[red]ERROR: DRC mode failed (result={result.get('result')})[/red]")
        else:
            console.print(f"\n[red]ERROR: Unexpected response type: expected dict, got {type(result)}[/red]")

    except TimeoutError as e:
        console.print(f"\n[red]ERROR: Timeout: {e}[/red]")
        console.print("[yellow]Possible causes:[/yellow]")
        console.print("[yellow]  1. MQTT response not received[/yellow]")
        console.print("[yellow]  2. Response format mismatch, Future not resolved[/yellow]")
        console.print("[yellow]  3. tid mismatch[/yellow]")
        mqtt_client.disconnect()
        return 1

    except Exception as e:
        console.print(f"\n[red]ERROR: {e}[/red]")
        console.print(f"[red]Exception type: {type(e).__name__}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        mqtt_client.disconnect()
        return 1

    # Cleanup
    console.print("\n[bold yellow][Cleanup] Disconnect[/bold yellow]")
    mqtt_client.disconnect()
    console.print("[green]OK: MQTT disconnected[/green]")

    console.print("\n[bold green]=======================================[/bold green]")
    console.print("[bold green]   Test Complete![/bold green]")
    console.print("[bold green]=======================================[/bold green]\n")

    return 0


if __name__ == '__main__':
    exit(main())
