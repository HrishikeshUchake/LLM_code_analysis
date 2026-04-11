#include <iostream>
#include <vector>
#include <string>
#include <cstdlib>
#include <bits/stdc++.h>
#include <mpi.h>

using namespace std;

int foo(int a, double b, int c, int p){    
    a = a/p; 
    
    for (int i = 0; i < a; ++i){c = i + c;}

    for (int i = 0; i < a; ++i)        
        c = i + c;  
    
    for (int i = 0; i < a; ++i){
        c = i;  
    }  
    
    a = a + c; 
    return a;
}

void bar(double x, int T){
    for (int i = 0; i < T; ++i)
        for (int j = 0; j < T; ++j)
            x = j + 1;  
    for (int i = 0; i < T; ++i){
        for (int j = 0; j < T; ++j){
            for (int k = 0; k < T; ++k){
                x = j + k;  
            }
        }
    }
}

int main(int argc, char* argv[]) {
    MPI_Init(&argc, &argv);

    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    double x = 1.0;
    int n = 5;
    int groups = 2;

    if (rank == 0)
    {
        for (int i = 1; i < argc - 1; i++)
        {
            if (std::string(argv[i]) == "-x")
                x = atof(argv[i + 1]);

            if (std::string(argv[i]) == "-n")
                n = atoi(argv[i + 1]);

            if (std::string(argv[i]) == "-g")
                groups = atoi(argv[i + 1]);
        }
    }

    MPI_Bcast(&n, 1, MPI_INT, 0, MPI_COMM_WORLD);
    
    std::vector<double> numbers(n);
    if (rank == 0)
    {
        for (int i = 0; i < n; ++i)
            numbers[i] = i + 1;  
    }

    MPI_Bcast(numbers.data(), n, MPI_DOUBLE, 0, MPI_COMM_WORLD);
    
    if (rank == 0) {
        if (n <= 0) {
            cerr << "MPI Error\n";
            MPI_Abort(MPI_COMM_WORLD, 1);
        }
        cout << "Input n = " << n << "\n";
    }   

    int T; 
    T = foo(n, x, groups, size);  
    bar(x, T); 

    MPI_Finalize();
    return 0;
}