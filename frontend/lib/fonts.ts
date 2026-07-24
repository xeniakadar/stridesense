import { Outfit } from "next/font/google";

// Brand display face — only the weights the Logo actually uses
export const outfit = Outfit({
  subsets: ["latin"],
  weight: ["600", "700"],
  display: "swap",
});
