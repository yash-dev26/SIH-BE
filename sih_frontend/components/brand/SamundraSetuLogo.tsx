import Image from "next/image";

export function SamundraSetuLogo({ className = "" }: { className?: string }) {
  return (
    <Image
      src="/brand/samundra-setu-mark.png"
      alt="Samundra Setu symbol"
      width={250}
      height={130}
      priority
      className={`h-auto w-10 object-contain brightness-0 invert ${className}`}
    />
  );
}
