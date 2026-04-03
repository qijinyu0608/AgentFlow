import argparse
import sys
import threading
import uvicorn
import webbrowser

from agentmesh.common import logger, load_config
from agentmesh.protocol import Task
from agentmesh.service.agent_executor import AgentExecutor


def list_available_teams(agent_executor: AgentExecutor):
    """List all available teams from configuration."""
    teams = agent_executor.list_available_teams()
    if not teams:
        print("No teams found in configuration.")
        return

    print("Available teams:")
    for team in teams:
        print(f"  - {team['name']}: {team['description']}")


def main():
    frozen = bool(getattr(sys, "frozen", False))

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="AgentMesh - Multi-Agent Framework")
    parser.add_argument("-t", "--team", help="Specify the team to run")
    parser.add_argument("-l", "--list", action="store_true", help="List available teams")
    parser.add_argument("-q", "--query", help="Direct query to run (non-interactive mode)")
    parser.add_argument("-s", "--server", action="store_true", help="Start API server")
    parser.add_argument("--host", default="127.0.0.1", help="API server host (default: 127.0.0.1)")
    parser.add_argument("-p", "--port", type=int, default=8001, help="API server port (default: 8001)")
    parser.add_argument("--open-browser", action="store_true", help="Open the Web UI in the default browser")
    args = parser.parse_args()

    if frozen and not any([args.team, args.list, args.query, args.server]):
        args.server = True
        args.open_browser = True

    # Load configuration
    load_config()
    agent_executor = AgentExecutor()

    # Start API server if requested
    if args.server:
        base_url = f"http://{args.host}:{args.port}"
        print("Starting AgentMesh API server...")
        print(f"Server will be available at: {base_url}")
        print(f"API documentation: {base_url}/docs")
        print("Press Ctrl+C to stop the server")
        if args.open_browser:
            threading.Timer(1.0, lambda: webbrowser.open(base_url)).start()
        try:
            uvicorn.run(
                "agentmesh.api.app:app",
                host=args.host,
                port=args.port,
                reload=not frozen,
                log_level="info"
            )
        except KeyboardInterrupt:
            print("\nServer stopped.")
        return

    # List teams if requested
    if args.list:
        list_available_teams(agent_executor)
        return

    # If no team is specified, show usage
    if not args.team:
        parser.print_help()
        return

    # Create team from configuration
    team = agent_executor.create_team_from_config(args.team)
    if not team:
        available_teams = agent_executor.list_available_teams()
        if available_teams:
            print(f"Available teams: {', '.join(team_info['name'] for team_info in available_teams)}")
        return

    # If a direct query is provided, run it in non-interactive mode
    if args.query:
        print(f"Team '{team.name}' loaded successfully.")
        print(f"User task: {args.query}")
        print()

        # Run the team with the user's query
        team.run(Task(content=args.query), output_mode="print")
        return

    # Otherwise, run in interactive mode
    print(f"Team '{team.name}' loaded successfully.")
    print(f"Description: {team.description}")
    print(f"Number of agents: {len(team.agents)}")
    print("\nEnter your task (type 'exit' to quit):")

    count = 0
    # Interactive loop
    while True:
        try:
            if count > 0:
                team = agent_executor.create_team_from_config(args.team)
            count += 1
            user_input = input("> ")
            if user_input.lower() in ["exit", "quit", "q"]:
                print("Exiting AgentMesh. Goodbye!")
                break

            if user_input.strip():
                # Run the team with the user's task
                team.run(Task(content=user_input), output_mode="print")
                print("\nEnter your next task (type 'exit' to quit):")
        except KeyboardInterrupt:
            print("\nExiting AgentMesh. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error: {e}")


if __name__ == "__main__":
    main()
