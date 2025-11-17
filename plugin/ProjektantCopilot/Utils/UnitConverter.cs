namespace ProjektantCopilot.Utils
{
    /// <summary>
    /// Unit conversion utilities.
    /// Revit uses imperial units (feet) internally, Czech codes use metric (mm).
    /// </summary>
    public static class UnitConverter
    {
        /// <summary>
        /// Convert feet to millimeters.
        /// </summary>
        public static double FeetToMillimeters(double feet)
        {
            return feet * 304.8;
        }

        /// <summary>
        /// Convert millimeters to feet.
        /// </summary>
        public static double MillimetersToFeet(double mm)
        {
            return mm / 304.8;
        }

        /// <summary>
        /// Convert square feet to square meters.
        /// </summary>
        public static double SquareFeetToSquareMeters(double sqft)
        {
            return sqft * 0.092903;
        }
    }
}
