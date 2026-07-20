using System;

namespace CodexDesktopPet
{
    internal static class LayoutMath
    {
        public static int Clamp(int value, int minimum, int maximum)
        {
            if (maximum < minimum) return minimum;
            return Math.Max(minimum, Math.Min(value, maximum));
        }

        public static void FitExpandedVertically(
            int anchorY,
            int workTop,
            int workBottom,
            int windowHeight,
            out int windowY,
            out int originY)
        {
            windowY = Clamp(anchorY - PetRenderer.DefaultFullOriginY, workTop, workBottom - windowHeight);
            originY = Clamp(anchorY - windowY, 39, 110);
        }
    }
}
