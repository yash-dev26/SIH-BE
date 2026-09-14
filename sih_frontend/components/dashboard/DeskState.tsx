export function DeskLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ice text-sm text-muted">
      Loading chartering desk…
    </div>
  );
}

export function DeskError({ message }: { message: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ice text-sm text-risk-high">{message}</div>
  );
}
