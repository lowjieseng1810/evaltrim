using AgentEval.Assertions;

internal static class Program
{
    private static int Main()
    {
        var passed = 0;
        var total = 0;
        total++;
        try
        {
            "hello-world".Should().Contain("hello");
            passed++;
            Console.WriteLine("contains_pos=1");
        }
        catch (Exception ex)
        {
            Console.WriteLine("contains_pos=0 " + ex.GetType().Name);
        }

        total++;
        try
        {
            "hello-world".Should().Contain("MISSING-TOKEN");
            Console.WriteLine("contains_neg=0");
        }
        catch (Exception)
        {
            passed++;
            Console.WriteLine("contains_neg=1");
        }

        total++;
        try
        {
            "abc123".Should().MatchPattern("[0-9]+");
            passed++;
            Console.WriteLine("regex_pos=1");
        }
        catch (Exception ex)
        {
            Console.WriteLine("regex_pos=0 " + ex.GetType().Name);
        }

        Console.WriteLine($"accuracy={(double)passed / total}");
        Console.WriteLine($"passed={passed}");
        Console.WriteLine($"total={total}");
        Console.WriteLine("package=AgentEval");
        Console.WriteLine("version=0.28.0-beta");
        return 0;
    }
}
