using System;
using System.Collections.Generic;
using System.Linq;

namespace CodexDesktopPet
{
    internal static class TaskStatus
    {
        public const string Idle = "idle";
        public const string Running = "running";
        public const string Approval = "approval";
        public const string Completed = "completed";
        public const string Cancelled = "cancelled";
        public const string Error = "error";
    }

    internal sealed class TaskSnapshot
    {
        public string SessionId = "";
        public string Status = TaskStatus.Idle;
        public string Phase = "会话就绪";
        public string Title = "Codex 任务";
        public string Cwd = "";
        public string TurnId = "";
        public double UpdatedAt;
        public double StartedAt;
        public string Source = "unknown";
        public string Provider = "codex";
        public bool? Unread;

        public TaskSnapshot Clone()
        {
            return (TaskSnapshot)MemberwiseClone();
        }
    }

    internal sealed class AggregateSnapshot
    {
        public string Status = TaskStatus.Idle;
        public TaskSnapshot Selected;
        public List<TaskSnapshot> Tasks = new List<TaskSnapshot>();
        public List<TaskSnapshot> VisibleTasks = new List<TaskSnapshot>();
        public int RunningCount;
        public int ApprovalCount;
        public int ErrorCount;
        public int CompletedCount;
        public int CancelledCount;

        public AggregateSnapshot Clone()
        {
            AggregateSnapshot copy = (AggregateSnapshot)MemberwiseClone();
            copy.Tasks = Tasks.Select(item => item.Clone()).ToList();
            copy.VisibleTasks = VisibleTasks.Select(item => item.Clone()).ToList();
            copy.Selected = Selected == null ? null : Selected.Clone();
            return copy;
        }
    }

    internal static class AggregateResolver
    {
        public static AggregateSnapshot Resolve(IEnumerable<TaskSnapshot> source, double now)
        {
            List<TaskSnapshot> ordered = source
                .OrderByDescending(item => item.UpdatedAt)
                .Select(item => item.Clone())
                .ToList();
            List<TaskSnapshot> approvals = ordered.Where(item => item.Status == TaskStatus.Approval && now - item.UpdatedAt <= 43200).ToList();
            List<TaskSnapshot> running = ordered.Where(item => item.Status == TaskStatus.Running && now - item.UpdatedAt <= 1800).ToList();
            List<TaskSnapshot> errors = ordered.Where(item => item.Status == TaskStatus.Error && now - item.UpdatedAt <= 3600).ToList();
            List<TaskSnapshot> cancelled = ordered.Where(item => item.Status == TaskStatus.Cancelled && now - item.UpdatedAt <= 600).ToList();
            List<TaskSnapshot> completed = ordered.Where(item =>
                item.Status == TaskStatus.Completed &&
                (item.Unread == true || (item.Unread == null && now - item.UpdatedAt <= 900))).ToList();

            AggregateSnapshot result = new AggregateSnapshot();
            result.Tasks = ordered;
            result.ApprovalCount = approvals.Count;
            result.RunningCount = running.Count;
            result.ErrorCount = errors.Count;
            result.CancelledCount = cancelled.Count;
            result.CompletedCount = completed.Count;
            if (approvals.Count > 0) { result.Status = TaskStatus.Approval; result.Selected = approvals[0]; }
            else if (running.Count > 0) { result.Status = TaskStatus.Running; result.Selected = running[0]; }
            else if (errors.Count > 0) { result.Status = TaskStatus.Error; result.Selected = errors[0]; }
            else if (cancelled.Count > 0) { result.Status = TaskStatus.Cancelled; result.Selected = cancelled[0]; }
            else if (completed.Count > 0) { result.Status = TaskStatus.Completed; result.Selected = completed[0]; }
            else { result.Status = TaskStatus.Idle; result.Selected = ordered.FirstOrDefault(item => item.Status == TaskStatus.Idle); }

            result.VisibleTasks.AddRange(approvals);
            result.VisibleTasks.AddRange(running);
            result.VisibleTasks.AddRange(errors);
            result.VisibleTasks.AddRange(cancelled);
            result.VisibleTasks.AddRange(completed);
            return result;
        }
    }
}
