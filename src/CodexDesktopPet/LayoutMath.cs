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

        public static bool ChooseBubbleOnRight(
            int anchorX,
            int workLeft,
            int workRight,
            int windowWidth,
            int originWhenBubbleLeft,
            int originWhenBubbleRight)
        {
            int leftLayoutX = anchorX - originWhenBubbleLeft;
            int rightLayoutX = anchorX - originWhenBubbleRight;
            bool leftFits = leftLayoutX >= workLeft && leftLayoutX + windowWidth <= workRight;
            bool rightFits = rightLayoutX >= workLeft && rightLayoutX + windowWidth <= workRight;
            if (rightFits && !leftFits) return true;
            if (leftFits && !rightFits) return false;
            return anchorX < workLeft + (workRight - workLeft) / 2;
        }
    }
}
