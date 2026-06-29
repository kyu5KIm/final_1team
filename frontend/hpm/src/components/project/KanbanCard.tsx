import { useState, type DragEvent } from "react";
import type { KanbanTask } from "../../types/kanban";

interface KanbanCardProps {
  task: KanbanTask;
  top: number;
  onClick: () => void;
  canManage?: boolean;
  isDragging?: boolean;
  onDragStart?: (task: KanbanTask) => void;
  onDragEnd?: () => void;
  onDropOnCard?: (task: KanbanTask) => void;
}

export default function KanbanCard({
  task,
  top,
  onClick,
  canManage = true,
  isDragging = false,
  onDragStart,
  onDragEnd,
  onDropOnCard,
}: KanbanCardProps) {
  const [isOver, setIsOver] = useState(false);

  const handleDragStart = (event: DragEvent<HTMLElement>) => {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", task.code);
    onDragStart?.(task);
  };

  const handleDragOver = (event: DragEvent<HTMLElement>) => {
    if (!canManage) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    if (!isOver) setIsOver(true);
  };

  const handleDragLeave = () => setIsOver(false);

  const handleDrop = (event: DragEvent<HTMLElement>) => {
    if (!canManage) return;
    event.preventDefault();
    event.stopPropagation();
    setIsOver(false);
    onDropOnCard?.(task);
  };

  return (
    <article
      draggable={canManage}
      onDragStart={handleDragStart}
      onDragEnd={() => {
        setIsOver(false);
        onDragEnd?.();
      }}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`flex ml-[23px] w-[306px] mb-[18px] select-none rounded-[10px] border-2 p-[14px] text-left transition-all duration-150 ease-out
      ${canManage ? "cursor-grab active:cursor-grabbing" : ""}
      ${isDragging ? "opacity-40 ring-2 ring-[#623FB5]" : ""}
      ${isOver ? "border-[#623FB5] bg-[#F2EEFB]" : "border-transparent bg-[#FFFDFD] hover:bg-[#F4F5F8]"}
      focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#623FB5]`}
      style={{ top }}
      data-name="dashboard=card"
    >
      <button
        type="button"
        onClick={canManage ? onClick : undefined}
        className={`rounded-[10px] border-0 bg-transparent p-0 text-left transition-all duration-150 ease-out focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#623FB5] ${
          canManage ? "active:scale-[0.985]" : "cursor-default"
        }`}
      >
        <div className="flex flex-col">
          <div className="flex w-full flex-col items-start gap-[10px]">
            <p className="m-0 w-[270px] text-[15px] font-normal leading-[1.2] text-[#141414]">
              {task.title}
            </p>
            <span className="flex h-[22px] items-center justify-center rounded-[20px] bg-[#DCD0FE] px-[8px] py-px text-[11px] font-normal leading-[1.2] text-[#623FB5]">
              {task.category}
            </span>
            <p className="m-0 text-[12px] font-normal leading-[1.2] text-[#969696]">
              {task.dueDate}
            </p>
          </div>
          <div className="mt-[18px] flex w-full justify-between items-center">
            <p className=" text-[12px] font-normal text-[#141414]">
              {task.code}
            </p>
            {task.owner !== "-" && (
              <p className="text-right text-[12px] font-normal text-[#969696]">
                {task.owner}
              </p>
            )}
          </div>
        </div>
      </button>
    </article>
  );
}
