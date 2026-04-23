"""命令行入口。"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4


def main() -> None:
    parser = argparse.ArgumentParser(description="video-maker: research + script pipeline")
    parser.add_argument("--topic", required=False, help="视频话题")
    parser.add_argument("--duration", default="1-3min", choices=["1-3min", "3-5min", "5-10min"], help="目标时长")
    parser.add_argument("--style", default="professional", choices=["professional", "casual", "storytelling"], help="旁白风格")
    parser.add_argument("--source", default="websearch", choices=["websearch", "notebooklm", "local-file", "manual"], help="素材来源")
    parser.add_argument("--aspect-ratio", default="16:9", choices=["16:9", "9:16", "3:4", "1:1"])
    parser.add_argument("--eval-mode", default="gan", choices=["gan", "legacy"], help="脚本评估模式")
    parser.add_argument("--project-root", default=".", help="输出根目录")
    parser.add_argument("--thread-id", default=None, help="恢复会话 ID")
    parser.add_argument("--notebook-url", default="", help="NotebookLM URL")
    parser.add_argument("--local-file", default="", help="本地素材文件路径")
    parser.add_argument("--validate-output-dir", default="", help="只校验指定 output_dir 下的 script artifacts")

    args = parser.parse_args()

    if args.validate_output_dir:
        from .validators import validate_script_artifacts

        result = validate_script_artifacts(args.validate_output_dir)
        print(f"[INFO] validate_output_dir: {args.validate_output_dir}")
        if result["all_errors"]:
            print("[FAIL] script artifact validation failed")
            for section in ("plan", "contract", "consistency"):
                for item in result[section]:
                    print(f"- [{section}] {item}")
            raise SystemExit(1)
        print("[OK] script artifact validation passed")
        return

    if not args.topic:
        parser.error("--topic is required unless --validate-output-dir is used")

    provider = os.getenv("LLM_PROVIDER", "deepseek")
    key_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "zhipu": "ANTHROPIC_API_KEY",
        "zhipu_openai": "ZHIPU_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    key_name = key_map.get(provider, "ANTHROPIC_API_KEY")
    if not os.getenv(key_name):
        sys.exit(f"[ERROR] {key_name} 未设置，请配置 .env 文件")

    from .producer import create_producer, init_output_dir
    from .tracing import attach_production_feedback, build_run_config

    output_dir = init_output_dir(args.topic, args.project_root)
    print(f"[INFO] 输出目录: {output_dir}")

    producer = create_producer(project_root=args.project_root)
    thread_id = args.thread_id or f"video-{Path(output_dir).name}"
    run_id = uuid4()

    config = build_run_config(
        thread_id=thread_id,
        run_id=run_id,
        topic=args.topic,
        duration=args.duration,
        style=args.style,
        eval_mode=args.eval_mode,
    )

    user_message = (
        f"请制作视频脚本。\n"
        f"topic: {args.topic}\n"
        f"source: {args.source}\n"
        f"duration: {args.duration}\n"
        f"style: {args.style}\n"
        f"aspect_ratio: {args.aspect_ratio}\n"
        f"eval_mode: {args.eval_mode}\n"
        f"output_dir: {output_dir}\n"
    )
    if args.notebook_url:
        user_message += f"notebook_url: {args.notebook_url}\n"
    if args.local_file:
        user_message += f"local_file: {args.local_file}\n"

    print(f"[INFO] 启动 Producer（thread_id={thread_id}, run_id={run_id}）...")

    async def _run():
        return await producer.ainvoke(
            {
                "messages": [{"role": "user", "content": user_message}],
                "output_dir": output_dir,
                "current_milestone": "research",
            },
            config=config,
        )

    result = asyncio.run(_run())

    attach_production_feedback(run_id, output_dir)

    if hasattr(result, "interrupts") and result.interrupts:
        print("\n[INFO] 流程已暂停，等待人工操作:")
        for interrupt in result.interrupts:
            print(f"  {interrupt}")
        print(f"\n恢复命令: python -m ll_video_maker.main --thread-id {thread_id} [其他参数]")


if __name__ == "__main__":
    main()
