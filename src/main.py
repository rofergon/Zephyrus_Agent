"""
Main entry point for the Zephyrus Agent application.
"""
import os
import sys
import asyncio
import signal
from loguru import logger

from .core.agent import Agent
from .config.settings import LOG_LEVEL, LOG_FILE


def setup_logging():
    """
    Set up logging configuration.
    """
    # Remove default logger
    logger.remove()
    
    # Add console logger
    logger.add(
        sys.stdout,
        level=LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add file logger
    logger.add(
        LOG_FILE,
        rotation="10 MB",
        retention="1 week",
        level=LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
    )


async def main():
    """
    Main entry point for the application.
    """
    # Set up logging
    setup_logging()
    
    logger.info("Starting Zephyrus Agent")
    
    # Create and start the agent
    agent = Agent()
    
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(agent, loop)))
    
    try:
        await agent.start()
        
        # Keep the application running
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.exception(f"Error in main loop: {e}")
        await shutdown(agent, loop)


async def shutdown(agent, loop):
    """
    Gracefully shut down the application.
    
    Args:
        agent: The agent instance
        loop: The event loop
    """
    logger.info("Shutting down Zephyrus Agent")
    
    # Stop the agent
    await agent.stop()
    
    # Cancel all tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    for task in tasks:
        task.cancel()
        
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Stop the event loop
    loop.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
    finally:
        logger.info("Zephyrus Agent stopped")
